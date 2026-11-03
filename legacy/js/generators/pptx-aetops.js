/**
 * Report Intelligence — Generador PPTX AETOPS (PptxGenJS)
 * Estructura alineada a reportes originales:
 * Mensual ~12 slides | Trimestral ~8 slides
 */

const COLORS = {
  primary: '1F4E79',
  primaryLight: '2E75B6',
  accent: '00A3A1',
  dark: '1A202C',
  muted: '64748B',
  white: 'FFFFFF',
  lightBg: 'F0F4F8',
  positive: '059669',
  negative: 'DC2626',
  tableHeader: '1F4E79',
  altRow: 'EBF2FA',
  disclaimer: '64748B',
};

function fmt(n, d = 0) {
  if (n == null || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString('es-MX', { maximumFractionDigits: d, minimumFractionDigits: d });
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return '—';
  const p = n * 100;
  return (p > 0 ? '+' : '') + p.toFixed(0) + '%';
}

function deltaColor(n) {
  if (n == null) return COLORS.muted;
  return n >= 0 ? COLORS.positive : COLORS.negative;
}

const DISCLAIMER = 'La información presentada es recopilada y gestionada por el Departamento de E-Commerce.';

export function generateAetopsPptx(data, config) {
  const pptxgen = window.PptxGenJS;
  if (!pptxgen) throw new Error('PptxGenJS no está cargado');

  const pptx = new pptxgen();
  pptx.defineLayout({ name: 'LAYOUT_16x9', width: 13.333, height: 7.5 });
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'Report Intelligence';
  pptx.title = `Resultados AETOPS ${config.periodLabel} ${config.year}`;

  const period = `${config.periodLabel} ${config.year}`;
  const isMonthly = config.periodicity === 'Mensual';
  let slideNum = 0;

  // ===== 1. Panorama General =====
  {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Panorama General', period);
    addDisclaimer(s, pptx);

    const kpis = data.kpis || [];
    const main = ['Monto Venta', 'Piezas', 'Pacientes', 'Pedidos'];
    const mainKpis = main.map(name => kpis.find(k => k.name === name)).filter(Boolean);

    mainKpis.forEach((kpi, i) => {
      const x = 0.4 + i * 3.2;
      s.addShape(pptx.ShapeType.roundRect, {
        x, y: 1.35, w: 3.05, h: 1.7,
        fill: { color: COLORS.lightBg }, rectRadius: 0.08,
      });
      s.addText(kpi.name, {
        x, y: 1.45, w: 3.05, h: 0.35,
        fontSize: 12, color: COLORS.muted, fontFace: 'Arial', align: 'center', margin: 0,
      });
      s.addText(fmt(kpi.actual), {
        x, y: 1.85, w: 3.05, h: 0.55,
        fontSize: 22, color: COLORS.primary, fontFace: 'Arial', bold: true, align: 'center', margin: 0,
      });
      s.addText(fmtPct(kpi.delta), {
        x, y: 2.5, w: 3.05, h: 0.35,
        fontSize: 14, color: deltaColor(kpi.delta), fontFace: 'Arial', bold: true, align: 'center', margin: 0,
      });
    });

    const sec = ['Ticket Promedio', 'Size B', 'V. Paciente', 'Productos Vendidos'];
    const secKpis = sec.map(name => kpis.find(k => k.name === name)).filter(Boolean);
    if (secKpis.length) {
      const rows = [
        headerRow(['Indicador', 'Actual', 'Anterior', '% Δ']),
        ...secKpis.map((k, i) => dataRow([
          k.name,
          fmt(k.actual, k.name === 'Size B' ? 2 : 0),
          fmt(k.previous, k.name === 'Size B' ? 2 : 0),
          fmtPct(k.delta),
        ], i, { deltaIdx: 3, deltaVal: k.delta })),
      ];
      s.addTable(rows, tableOpts(0.4, 3.4, 12.5, [4.0, 2.8, 2.8, 2.9]));
    }
    addFooter(s, pptx, slideNum);
  }

  // ===== 2. Líneas =====
  if (data.byLine?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Análisis Líneas AETOP', period);
    addDisclaimer(s, pptx);

    const rows = [
      headerRow(['Línea', 'Monto Actual', 'Monto Anterior', '% Δ', 'Share']),
      ...data.byLine.map((l, i) => dataRow([
        l.linea,
        '$' + fmt(l.montoActual),
        '$' + fmt(l.montoAnterior),
        fmtPct(l.deltaMonto),
        l.shareActual != null ? (l.shareActual * 100).toFixed(0) + '%' : '—',
      ], i, { deltaIdx: 3, deltaVal: l.deltaMonto })),
    ];
    s.addTable(rows, tableOpts(0.4, 1.35, 12.5, [2.0, 2.8, 2.8, 2.2, 2.7]));

    if (data.byLine.some(l => l.montoActual != null)) {
      const labels = data.byLine.map(l => l.linea);
      s.addChart(pptx.charts.BAR, [
        { name: 'Actual', labels, values: data.byLine.map(l => l.montoActual || 0) },
        { name: 'Anterior', labels, values: data.byLine.map(l => l.montoAnterior || 0) },
      ], {
        x: 0.4, y: 3.6, w: 12.5, h: 3.2,
        barDir: 'col', barGrouping: 'clustered', showLegend: true, legendPos: 'b',
        chartColors: [COLORS.primary, '5B9BD5'],
      });
    }
    addFooter(s, pptx, slideNum);
  }

  // ===== 3. Canales =====
  if (data.byChannel?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Análisis Canales de Venta', period);
    addDisclaimer(s, pptx);

    const rows = [
      headerRow(['Canal', 'Monto Actual', 'Monto Anterior', '% Δ', 'Share']),
      ...data.byChannel.map((c, i) => dataRow([
        c.canal,
        '$' + fmt(c.montoActual),
        '$' + fmt(c.montoAnterior),
        fmtPct(c.deltaMonto),
        c.shareActual != null ? (c.shareActual * 100).toFixed(0) + '%' : '—',
      ], i, { deltaIdx: 3, deltaVal: c.deltaMonto })),
    ];
    s.addTable(rows, tableOpts(0.4, 1.35, 12.5, [3.2, 2.5, 2.5, 2.0, 2.3]));

    if (data.byChannel.some(c => c.montoActual != null)) {
      const labels = data.byChannel.map(c => c.canal);
      s.addChart(pptx.charts.BAR, [
        { name: 'Actual', labels, values: data.byChannel.map(c => c.montoActual || 0) },
        { name: 'Anterior', labels, values: data.byChannel.map(c => c.montoAnterior || 0) },
      ], {
        x: 0.4, y: 3.5, w: 12.5, h: 3.3,
        barDir: 'col', barGrouping: 'clustered', showLegend: true, legendPos: 'b',
        chartColors: [COLORS.primary, '5B9BD5'],
      });
    }
    addFooter(s, pptx, slideNum);
  }

  // ===== 4. Causas de la caída (si hay datos) =====
  if (data.causas?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Causas de la caída en canales', period);
    addDisclaimer(s, pptx);

    const rows = [
      headerRow(['Canal', 'Δ Total', 'Producto no vendido', '# Productos', 'Residual']),
      ...data.causas.map((c, i) => dataRow([
        c.canal,
        '$' + fmt(c.totalDelta),
        '$' + fmt(c.productoNoVendido),
        fmt(c.countProductosNoVendidos),
        '$' + fmt(c.residual),
      ], i)),
    ];
    s.addTable(rows, tableOpts(0.4, 1.4, 12.5, [3.0, 2.3, 2.8, 2.0, 2.4]));
    s.addText('Nota: desglose basado en detalle Producto × Canal cuando está disponible. Residual incluye cambios de pacientes, piezas y ticket.', {
      x: 0.4, y: 3.5, w: 12.5, h: 0.5,
      fontSize: 11, color: COLORS.muted, fontFace: 'Arial', margin: 0,
    });
    addFooter(s, pptx, slideNum);
  }

  // ===== 5. Productos crecimiento =====
  if (data.ranking?.growth?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Análisis de Productos — Crecimiento', period);
    addDisclaimer(s, pptx);
    addProductTable(s, pptx, data.ranking.growth.slice(0, 12));
    addFooter(s, pptx, slideNum);
  }

  // ===== 6. Productos caída =====
  if (data.ranking?.decline?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Análisis de Productos — Caída', period);
    addDisclaimer(s, pptx);
    addProductTable(s, pptx, data.ranking.decline.slice(0, 12), true);
    addFooter(s, pptx, slideNum);
  }

  // ===== 7. Negados =====
  if (data.negados?.totalMonto != null || data.negados?.topProducts?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Análisis de Negados', period);
    addDisclaimer(s, pptx);

    s.addShape(pptx.ShapeType.roundRect, {
      x: 0.4, y: 1.35, w: 4.2, h: 1.15,
      fill: { color: 'FEF2F2' }, rectRadius: 0.08,
    });
    s.addText('Monto Negado Total', {
      x: 0.4, y: 1.45, w: 4.2, h: 0.3,
      fontSize: 12, color: COLORS.muted, fontFace: 'Arial', align: 'center', margin: 0,
    });
    s.addText('$' + fmt(data.negados.totalMonto), {
      x: 0.4, y: 1.8, w: 4.2, h: 0.5,
      fontSize: 22, color: COLORS.negative, fontFace: 'Arial', bold: true, align: 'center', margin: 0,
    });

    const items = (data.negados.topProducts || []).slice(0, 10);
    if (items.length) {
      const rows = [
        headerRow(['Producto', 'Línea', 'Monto Negado', 'Share']),
        ...items.map((p, i) => dataRow([
          (p.producto || '').substring(0, 42),
          p.linea || '—',
          '$' + fmt(p.montoNegado),
          p.share != null ? (p.share * 100).toFixed(1) + '%' : '—',
        ], i)),
      ];
      s.addTable(rows, tableOpts(0.4, 2.75, 12.5, [6.2, 1.8, 2.5, 2.0]));
    }
    addFooter(s, pptx, slideNum);
  }

  // ===== 8. Conclusiones (plantilla estructural) =====
  {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Conclusiones Clave', period);
    addDisclaimer(s, pptx);

    const bullets = buildConclusions(data, config);
    bullets.forEach((b, i) => {
      s.addShape(pptx.ShapeType.roundRect, {
        x: 0.4, y: 1.35 + i * 0.95, w: 12.5, h: 0.85,
        fill: { color: i % 2 ? COLORS.altRow : COLORS.lightBg }, rectRadius: 0.06,
      });
      s.addText(b, {
        x: 0.6, y: 1.45 + i * 0.95, w: 12.1, h: 0.65,
        fontSize: 13, color: COLORS.dark, fontFace: 'Arial', margin: 0, valign: 'middle',
      });
    });
    addFooter(s, pptx, slideNum);
  }

  const fileName = `Resultados_AETOPS_${config.periodLabel}_${config.year}.pptx`.replace(/\s+/g, '_');
  return pptx.writeFile({ fileName });
}

function buildConclusions(data, config) {
  const out = [];
  const monto = data.kpis?.find(k => k.name === 'Monto Venta');
  if (monto) {
    out.push(`El monto de venta ${monto.delta >= 0 ? 'creció' : 'disminuyó'} ${fmtPct(monto.delta)} vs periodo anterior (Actual: $${fmt(monto.actual)}).`);
  }
  if (data.byLine?.length) {
    const top = [...data.byLine].sort((a, b) => (b.montoActual || 0) - (a.montoActual || 0))[0];
    if (top) out.push(`La línea ${top.linea} concentra el mayor monto ($${fmt(top.montoActual)}, share ${top.shareActual != null ? (top.shareActual * 100).toFixed(0) + '%' : '—'}).`);
  }
  if (data.byChannel?.length) {
    const top = [...data.byChannel].sort((a, b) => (b.deltaMonto || 0) - (a.deltaMonto || 0))[0];
    if (top) out.push(`El canal con mejor variación es ${top.canal} (${fmtPct(top.deltaMonto)}).`);
  }
  if (data.negados?.totalMonto) {
    out.push(`El monto negado asciende a $${fmt(data.negados.totalMonto)}. Revisar disponibilidad de top productos negados.`);
  }
  if (out.length < 3) {
    out.push('Revisar el detalle de productos y canales en las diapositivas anteriores para identificar drivers y riesgos.');
  }
  return out.slice(0, 5);
}

function addProductTable(slide, pptx, items, isDecline = false) {
  const rows = [
    headerRow(['#', 'Producto', 'Línea', 'Actual', 'Anterior', 'Δ $']),
    ...items.map((p, i) => dataRow([
      String(i + 1),
      (p.producto || '').substring(0, 42),
      p.linea || '—',
      '$' + fmt(p.actual),
      '$' + fmt(p.previous),
      (p.delta >= 0 ? '+' : '') + '$' + fmt(p.delta),
    ], i, { deltaIdx: 5, deltaVal: p.delta })),
  ];
  slide.addTable(rows, tableOpts(0.35, 1.35, 12.6, [0.55, 5.3, 1.3, 1.8, 1.8, 1.85]));
}

function headerRow(cols) {
  return cols.map(t => ({
    text: t,
    options: { bold: true, color: COLORS.white, fill: { color: COLORS.tableHeader }, align: 'center' },
  }));
}

function dataRow(cols, i, opts = {}) {
  const bg = i % 2 ? COLORS.altRow : COLORS.white;
  return cols.map((t, idx) => {
    const o = { fill: { color: bg }, align: idx <= 1 ? 'left' : 'center' };
    if (opts.deltaIdx === idx && opts.deltaVal != null) {
      o.color = deltaColor(opts.deltaVal);
      o.bold = true;
    }
    return { text: t, options: o };
  });
}

function tableOpts(x, y, w, colW) {
  return {
    x, y, w, colW,
    border: [{ pt: 0.5, color: 'D0D7DE' }],
    fontFace: 'Arial', fontSize: 11,
    color: COLORS.dark, align: 'center', valign: 'middle',
  };
}

function addHeader(slide, pptx, title, period) {
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 13.333, h: 0.75,
    fill: { color: COLORS.primary },
  });
  slide.addText(title, {
    x: 0.4, y: 0.15, w: 9, h: 0.45,
    fontSize: 18, color: COLORS.white, fontFace: 'Arial', bold: true, margin: 0,
  });
  slide.addText(period, {
    x: 9.5, y: 0.2, w: 3.5, h: 0.35,
    fontSize: 12, color: 'A0C4E8', fontFace: 'Arial', align: 'right', margin: 0,
  });
}

function addDisclaimer(slide, pptx) {
  slide.addText(DISCLAIMER, {
    x: 0.4, y: 0.8, w: 12.5, h: 0.3,
    fontSize: 9, color: COLORS.disclaimer, fontFace: 'Arial', italic: true, margin: 0,
  });
}

function addFooter(slide, pptx, num) {
  slide.addText(`Report Intelligence  ·  ${num}`, {
    x: 0.4, y: 7.15, w: 12.5, h: 0.25,
    fontSize: 10, color: COLORS.muted, fontFace: 'Arial', align: 'right', margin: 0,
  });
}
