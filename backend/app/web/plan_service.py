"""Bloque integral en la capa de servicio: escenarios, plan de la corrida, vigencia por huella, vista previa y estado de exportación.

Está FUERA de `service.py` (archivo protegido) para que este conserve solo los puntos de conexión indispensables: `generate` llama a `preparar`,
`result_info` a `estado_resultado` y `file_path` a `verificar_descarga`. Importa `service` en el arranque y `service` importa este módulo solo dentro de sus
funciones (sin ciclos). Todo lo que necesita de `service` lo toma de `S` en el momento de la llamada, de modo que `importlib.reload(service)` (pruebas) sigue válido."""
from __future__ import annotations

import hashlib
import json

from ..history import store as hist
from ..plan import escenario as plan_esc, flujo as plan_flujo
from . import service as S

ARCHIVOS = ("plan_reporte.json", "slidespec.json", "previsualizacion.json", "qa_integral.json")


# ------------------------------------------------------------------ bloque integral: escenarios, SlideSpec, diseño adaptativo, QA integral y vista previa
def _con_historial():
    return hist.connect(S.HISTORY_DB)


def _escenario_de(st: dict):
    """Escenario efectivo de la corrida: el elegido (o el del perfil) con los ajustes de esta corrida. Un id que ya no existe es un error, no un silencio."""
    sel = st.get("plan") or {}
    id_ = sel.get("escenario_id") or plan_esc.id_para_perfil(st["unit"], st["periodicity"])
    con = _con_historial()
    try:
        base = plan_esc.todos(con).get(id_)
    finally:
        con.close()
    if base is None:
        raise S.ServiceError(f"El escenario «{id_}» ya no existe: elige otro.", 409)
    try:
        return plan_esc.ajustar(base, sel.get("cambios"))
    except plan_esc.ErrorEscenario as e:
        raise S.ServiceError(f"Escenario no válido: {e}", 400) from None


def _contexto_efectivo(st: dict, esc) -> list[str]:
    """Contexto aportado por el equipo + el contexto de negocio del escenario (mismas reglas: texto del equipo, no verificado, máx. 6 líneas)."""
    base = list(st["context"])
    return (base + [x[:600] for x in plan_esc.lineas_contexto(esc) if x[:600] not in base])[:6]


def _indicadores(res, st: dict) -> dict:
    """Estado de cada indicador relevante: su valor o None (no disponible). Solo AETOPS expone indicadores del panorama."""
    nombres = {"Venta": "monto", "Pacientes": "pacientes", "Ticket": "ticket", "Piezas": "piezas"}
    return {nombres[k["metrica"]]: k["valor"] for k in S._kpis(res, st) if k["metrica"] in nombres}


def _huella_entradas(run_id: str, st: dict) -> str:
    """Huella de TODO lo que determina el reporte: libro, ediciones, contexto, metas, descubrimiento, escenario efectivo, opciones y plantilla."""
    inp = S._dir(run_id) / "input.xlsx"
    try:
        tpl = hashlib.sha256(S.template_path(st).read_bytes()).hexdigest()
    except (S.ServiceError, OSError):
        tpl = None
    sel = st.get("plan") or {}
    try:
        esc_huella = _escenario_de(st).huella()
    except S.ServiceError:
        esc_huella = "escenario-inexistente"                                # un escenario borrado o inválido invalida lo generado: nunca se asume vigente
    return plan_flujo.huella_de(hashlib.sha256(inp.read_bytes()).hexdigest() if inp.exists() else None, st["edits"], st["context"], st["targets"], st.get("discovery"),
                                esc_huella, sel.get("adaptativo", True), sel.get("anexo"), tpl)


def _vigencia(run_id: str) -> dict:
    """{"vigente": True | False | None, "motivos": [...]}. None = reporte generado antes del flujo integrado (sin vista previa ni QA integral): no se bloquea."""
    out = S._dir(run_id) / "out"
    if not (out / "plan_reporte.json").exists():
        return {"vigente": None, "motivos": ["Reporte generado antes del flujo integrado: no tiene vista previa ni QA integral."]}
    return plan_flujo.vigente(out, _huella_entradas(run_id, S._load(run_id)))


def escenarios_reporte() -> dict:
    con = _con_historial()
    try:
        propios = plan_esc.listar_propios(con)
    finally:
        con.close()
    try:
        cat = plan_esc.catalogo()
    except plan_esc.ErrorEscenario as e:
        raise S.ServiceError(str(e), 500) from None
    return {"catalogo": [e.to_dict() for e in cat.values()], "propios": [e.to_dict() for e in propios.values()],
            "opciones": {"profundidades": list(plan_esc.PROFUNDIDADES), "tipos_conclusion": list(plan_esc.TIPOS_CONCLUSION),
                         "tipos_diapositiva": list(plan_esc.TIPOS_DIAPOSITIVA), "indicadores": list(plan_esc.INDICADORES), "max_texto": plan_esc.MAX_TEXTO}}


def guardar_escenario(body: dict) -> dict:
    con = _con_historial()
    try:
        return plan_esc.guardar_propio(con, body or {}).to_dict()
    except plan_esc.ErrorEscenario as e:
        raise S.ServiceError(str(e), 400) from None
    finally:
        con.close()


def borrar_escenario(id_: str) -> dict:
    con = _con_historial()
    try:
        if not plan_esc.borrar_propio(con, id_):
            raise S.ServiceError("No existe un escenario propio con ese id (los del catálogo no se borran).", 404)
    finally:
        con.close()
    return {"borrado": id_}


def set_plan(run_id: str, body: dict) -> dict:
    """Elige el escenario de la corrida (y sus ajustes) y si el diseño adaptativo está activo. Se valida AL GUARDAR, no al generar."""
    st = S._load(run_id)
    body = body or {}
    sel = dict(st.get("plan") or {})
    if "escenario_id" in body:
        sel["escenario_id"] = body["escenario_id"] or None
        sel["cambios"] = None if "cambios" not in body else sel.get("cambios")
    if "cambios" in body:
        if body["cambios"] is not None and not isinstance(body["cambios"], dict):
            raise S.ServiceError("«cambios» debe ser un objeto.")
        sel["cambios"] = body["cambios"] or None
    if "adaptativo" in body:
        sel["adaptativo"] = bool(body["adaptativo"])
    anterior = st.get("plan")
    st["plan"] = sel
    try:
        _escenario_de(st)                                                  # valida el escenario efectivo
    except S.ServiceError:
        st["plan"] = anterior
        raise
    S._save(run_id, st)
    return plan_info(run_id)


def plan_info(run_id: str) -> dict:
    st = S._load(run_id)
    esc = _escenario_de(st)
    out = S._dir(run_id) / "out"
    sel = st.get("plan") or {}
    r = {"escenario": esc.to_dict(), "no_definidos": esc.no_definidos(), "escenario_id": sel.get("escenario_id") or plan_esc.id_para_perfil(st["unit"], st["periodicity"]),
         "cambios": sel.get("cambios"), "adaptativo": sel.get("adaptativo", True), "generado": (out / "plan_reporte.json").exists()}
    if r["generado"]:
        vig = _vigencia(run_id)
        r.update(vigente=vig["vigente"], motivos=vig["motivos"])
        r["diseno"] = json.loads((out / "plan_reporte.json").read_text(encoding="utf-8")).get("diseno")
        r["qa_integral"] = json.loads((out / "qa_integral.json").read_text(encoding="utf-8"))
        r["diapositivas"] = [{k: d[k] for k in ("id", "tipo", "titulo", "indice", "densidad", "estado", "avisos", "mensaje")}
                             for d in json.loads((out / "slidespec.json").read_text(encoding="utf-8"))["diapositivas"]]
    return r


def vista_previa(run_id: str) -> dict:
    """Vista previa del reporte generado. Si el reporte cambió desde entonces NO se entrega (no se muestra información desactualizada): 409."""
    out = S._dir(run_id) / "out"
    if not (out / "previsualizacion.json").exists():
        raise S.ServiceError("Aún no hay vista previa: genera el reporte.", 404)
    vig = _vigencia(run_id)
    if vig["vigente"] is not True:
        raise S.ServiceError("La vista previa está desactualizada: " + " ".join(vig["motivos"]) + " Vuelve a generar el reporte.", 409)
    return json.loads((out / "previsualizacion.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ puntos de conexión que usa service.py
def preparar(run_id: str, st: dict, res, anexo: bool | None, adaptativo: bool | None):
    """Antes de construir el PPTX: guarda las opciones en la corrida (forman parte de la huella de lo generado) y devuelve `(plan, contexto)`:
    el `Plan` integral y el contexto efectivo (el del equipo + el de negocio del escenario)."""
    sel = dict(st.get("plan") or {})
    if adaptativo is not None:
        sel["adaptativo"] = bool(adaptativo)
    sel["anexo"] = anexo
    st["plan"] = sel
    S._save(run_id, st)
    esc = _escenario_de(st)
    plan = plan_flujo.Plan(esc, f"{st['unit']}/{st['periodicity']}", [st.get("filename") or "input.xlsx"], sel.get("adaptativo", True),
                           _indicadores(res, st), huella_entradas=_huella_entradas(run_id, st))
    return plan, _contexto_efectivo(st, esc)


def estado_resultado(run_id: str, qa_ok: bool) -> dict:
    """Campos que `result_info` agrega: vigencia, motivos, resumen del QA integral y `downloadable` (un reporte desactualizado no se descarga)."""
    vig = _vigencia(run_id)
    qi = S._dir(run_id) / "out" / "qa_integral.json"
    resumen = None
    if qi.exists():
        d = json.loads(qi.read_text(encoding="utf-8"))
        resumen = {"estado": d["estado"], "resumen": d["resumen"], "exportable": d["exportable"]}
    return {"downloadable": bool(qa_ok) and vig["vigente"] is not False, "vigente": vig["vigente"], "motivos_obsoleto": vig["motivos"], "qa_integral": resumen}


def verificar_descarga(run_id: str, name: str) -> None:
    """Bloquea la descarga del PPTX/PDF si el reporte cambió después de generarlo. Un reporte anterior al flujo integral (`vigente: None`) no se bloquea."""
    if name.lower().endswith((".pptx", ".pdf")) and _vigencia(run_id)["vigente"] is False:
        raise S.ServiceError("Descarga bloqueada: el reporte cambió después de generarlo (su QA y su vista previa están desactualizados). Vuelve a generarlo.", 403)
