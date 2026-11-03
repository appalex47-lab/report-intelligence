"""PPTX -> PDF (LibreOffice headless) -> PNG. Un solo render para PDF y para QA visual.

La fuente "Aptos Narrow" no está disponible ni es redistribuible: SOLO para el render se sustituye por
Carlito (ver docker/fonts.conf y docs/ARQUITECTURA.md §9.5). El PPTX conserva Aptos Narrow.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

FONTS_CONF = Path(__file__).resolve().parents[2] / "docker" / "fonts.conf"


class RenderError(Exception):
    pass


def convert_to_pdf(pptx: Path, out_dir: Path, timeout: int = 240) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RenderError("LibreOffice (soffice) no está instalado.")
    env = dict(os.environ, FONTCONFIG_FILE=str(FONTS_CONF), HOME=tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="lo_profile_") as prof:
        cmd = [soffice, f"-env:UserInstallation=file://{prof}", "--headless", "--convert-to", "pdf",
               "--outdir", str(out_dir), str(pptx)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as e:
            raise RenderError("LibreOffice excedió el tiempo límite.") from e
        except subprocess.CalledProcessError as e:
            raise RenderError(f"LibreOffice falló: {e.stderr.decode(errors='ignore')[:300]}") from e
    pdf = out_dir / (pptx.stem + ".pdf")
    if not pdf.exists():
        raise RenderError("LibreOffice no generó el PDF.")
    return pdf


def pdf_to_pngs(pdf: Path, out_dir: Path, dpi: int = 60) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / pdf.stem
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(prefix)], check=True, capture_output=True)
    return sorted(out_dir.glob(f"{pdf.stem}-*.png"))
