/**
 * Report Intelligence — Generador PPTX GLP-1 (PptxGenJS)
 * Estructura alineada a reportes originales (~11 slides)
 */

const COLORS = {
  primary: '1F4E79',
  primaryLight: '2E75B6',
  dark: '1A202C',
  muted: '64748B',
  white: 'FFFFFF',
  lightBg: 'F0F4F8',
  positive: '059669',
  negative: 'DC2626',
  tableHeader: '1F4E79',
  altRow: 'EBF2FA',
};

const DISCLAIMER = 'La información presentada es recopilada y gestionada por el Departamento de E-Commerce.';

function fmt(n, d = 0) {
  if (n == null || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString('es-MX', { maximumFractionDigits: d, minimumFractionDigits: d });
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return '—';
  const p = Math.abs(n) < 2 ? n * 100 : n;
  return (p > 0 ? '+' : '') + Number(p).toFixed(0) + '%';
}

function deltaColor(n) {
  if (n == null) return COLORS.muted;
  return n >= 0 ? COLORS.positive : COLORS.negative;
}

export function generateGlp1Pptx(data, config) {
  const pptxgen = window.PptxGenJS;
  if (!pptxgen) throw new Error('PptxGenJS no está cargado');

  const pptx = new pptxgen();
  pptx.defineLayout({ name: 'LAYOUT_16x9', width: 13.333, height: 7.5 });
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'Report Intelligence';
  pptx.title = `Resultados GLP-1 ${config.periodLabel} ${config.year}`;

  const period = `${config.periodLabel} ${config.year}`;
  let slideNum = 0;

  // 1. Portada conceptual — ¿Quién busca?
  {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, '¿Quién busca GLP-1?', period);
    addDisclaimer(s, pptx);

    const demo = (data.raw?.demography || []).filter(d => d.dimension === 'Edad');
    if (demo.length) {
      const rows = [
        headerRow(['Edad', 'Visitas', 'Usuarios', 'Add to Cart', 'Recurrentes', 'Nuevos']),
        ...demo.slice(0, 8).map((d, i) => dataRow([
          d.value,
          fmt(d.visitasActual),
          fmt(d.usuariosActual),
          fmt(d.addToCartActual),
          fmt(d.recurrentesActual),
          fmt(d.nuevosActual),
        ], i)),
      ];
      s.addTable(rows, tableOpts(0.35, 1.3, 12.6, [2.0, 2.1, 2.1, 2.1, 2.15, 2.15]));
    } else if (data.summary?.length) {
      data.summary.forEach((row, i) => {
        const x = 0.4 + (i % 4) * 3.2;
        const y = 1.4 + Math.floor(i / 4) * 1.7;
        s.addShape(pptx.ShapeType.roundRect, {
          x, y, w: 3.05, h: 1.5, fill: { color: COLORS.lightBg }, rectRadius: 0.08,
        });
        s.addText(row.label, {
          x, y: y + 0.2, w: 3.05, h: 0.4,
          fontSize: 11, color: COLORS.muted, fontFace: 'Arial', align: 'center', margin: 0,
        });
        s.addText(fmt(row.value), {
          x, y: y + 0.7, w: 3.05, h: 0.5,
          fontSize: 18, color: COLORS.primary, fontFace: 'Arial', bold: true, align: 'center', margin: 0,
        });
      });
    }
    addFooter(s, pptx, slideNum);
  }

  // 2. Regiones
  if (data.regions?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Venta por Región', period);
    addDisclaimer(s, pptx);

    const items = data.regions.filter(r => (r.montoActual || 0) > 5000).slice(0, 10);
    const rows = [
      headerRow(['Región', 'Pedidos', 'Monto Venta', 'Pacientes', 'Ticket', '% Δ']),
      ...items.map((r, i) => dataRow([
        r.region,
        fmt(r.pedidosActual),
        '$' + fmt(r.montoActual),
        fmt(r.pacientesActual),
        fmt(r.ticketActual),
        fmtPct(r.delta),
      ], i, { deltaIdx: 5, deltaVal: r.delta })),
    ];
    s.addTable(rows, tableOpts(0.35, 1.3, 12.6, [2.8, 1.8, 2.5, 1.8, 1.8, 1.9]));

    if (items.length) {
      s.addChart(pptx.charts.BAR, {
        x: 0.35, y: 4.3, w: 12.6, h: 2.5,
        showLegend: false, chartColors: [COLORS.primary],
        categories: items.map(r => r.region),
        series: [{ name: 'Monto', values: items.map(r => r.montoActual || 0) }],
      });
    }
    addFooter(s, pptx, slideNum);
  }

  // 3. Formas de pago
  if (data.payment?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Comportamiento de Compra — Formas de Pago', period);
    addDisclaimer(s, pptx);

    const rows = [
      headerRow(['Forma de Pago', 'Monto', 'Pedidos', 'Pacientes', 'Share']),
      ...data.payment.map((p, i) => dataRow([
        p.formaPago,
        '$' + fmt(p.montoActual),
        fmt(p.pedidosActual),
        fmt(p.pacientesActual),
        p.shareActual != null ? (p.shareActual * 100).toFixed(0) + '%' : (p.share != null ? (Math.abs(p.share) < 2 ? p.share * 100 : p.share).toFixed(0) + '%' : '—'),
      ], i)),
    ];
    s.addTable(rows, tableOpts(0.35, 1.3, 12.6, [4.5, 2.3, 2.0, 2.0, 1.8]));
    addFooter(s, pptx, slideNum);
  }

  // 4. Productos
  if (data.products?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Comportamiento de Compra — Productos', period);
    addDisclaimer(s, pptx);

    const items = data.products.slice(0, 12);
    const rows = [
      headerRow(['#', 'Producto', 'Monto', 'Pedidos', 'Pacientes', '% Δ']),
      ...items.map((p, i) => dataRow([
        String(i + 1),
        (p.producto || '').substring(0, 48),
        '$' + fmt(p.montoActual),
        fmt(p.pedidosActual),
        fmt(p.pacientesActual),
        fmtPct(p.deltaPct ?? p.delta),
      ], i, { deltaIdx: 5, deltaVal: p.deltaPct ?? p.delta })),
    ];
    s.addTable(rows, tableOpts(0.3, 1.3, 12.7, [0.55, 5.8, 2.0, 1.5, 1.5, 1.35]));
    addFooter(s, pptx, slideNum);
  }

  // 5. Negados
  if (data.negados?.totalMonto != null || data.negados?.items?.length) {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Negados', period);
    addDisclaimer(s, pptx);

    s.addShape(pptx.ShapeType.roundRect, {
      x: 0.35, y: 1.3, w: 4.2, h: 1.1,
      fill: { color: 'FEF2F2' }, rectRadius: 0.08,
    });
    s.addText('Monto Negado Total', {
      x: 0.35, y: 1.4, w: 4.2, h: 0.3,
      fontSize: 12, color: COLORS.muted, fontFace: 'Arial', align: 'center', margin: 0,
    });
    s.addText('$' + fmt(data.negados.totalMonto), {
      x: 0.35, y: 1.75, w: 4.2, h: 0.45,
      fontSize: 20, color: COLORS.negative, fontFace: 'Arial', bold: true, align: 'center', margin: 0,
    });

    const items = (data.negados.items || []).slice(0, 10);
    if (items.length) {
      const rows = [
        headerRow(['Producto', 'Monto Negado', 'Pedidos', 'Piezas']),
        ...items.map((p, i) => dataRow([
          (p.producto || '').substring(0, 50),
          '$' + fmt(p.montoNegado),
          fmt(p.pedidos),
          fmt(p.piezas),
        ], i)),
      ];
      s.addTable(rows, tableOpts(0.35, 2.65, 12.6, [7.0, 2.3, 1.7, 1.6]));
    }
    addFooter(s, pptx, slideNum);
  }

  // 6. Conclusiones
  {
    slideNum++;
    const s = pptx.addSlide();
    addHeader(s, pptx, 'Conclusiones Clave', period);
    addDisclaimer(s, pptx);

    const bullets = [];
    if (data.products?.length) {
      const top = data.products[0];
      bullets.push(`${(top.producto || '').substring(0, 50)} lidera la venta con $${fmt(top.montoActual)}.`);
    }
    if (data.regions?.length) {
      const top = [...data.regions].sort((a, b) => (b.montoActual || 0) - (a.montoActual || 0))[0];
      if (top) bullets.push(`La región ${top.region} concentra el mayor monto ($${fmt(top.montoActual)}).`);
    }
    if (data.negados?.totalMonto) {
      bullets.push(`Monto negado total: $${fmt(data.negados.totalMonto)}. Oportunidad de recuperación en disponibilidad.`);
    }
    if (data.payment?.length) {
      const top = data.payment[0];
      bullets.push(`Forma de pago principal: ${top.formaPago} ($${fmt(top.montoActual)}).`);
    }
    if (!bullets.length) bullets.push('Revisar las diapositivas anteriores para el detalle de demografía, regiones y productos.');

    bullets.slice(0, 5).forEach((b, i) => {
      s.addShape(pptx.ShapeType.roundRect, {
        x: 0.35, y: 1.3 + i * 0.95, w: 12.6, h: 0.85,
        fill: { color: i % 2 ? COLORS.altRow : COLORS.lightBg }, rectRadius: 0.06,
      });
      s.addText(b, {
        x: 0.55, y: 1.4 + i * 0.95, w: 12.2, h: 0.65,
        fontSize: 13, color: COLORS.dark, fontFace: 'Arial', margin: 0, valign: 'middle',
      });
    });
    addFooter(s, pptx, slideNum);
  }

  const fileName = `Resultados_GLP1_${config.periodLabel}_${config.year}.pptx`.replace(/\s+/g, '_');
  return pptx.writeFile({ fileName });
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
    return { text: String(t), options: o };
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
    x: 0.35, y: 0.15, w: 9, h: 0.45,
    fontSize: 18, color: COLORS.white, fontFace: 'Arial', bold: true, margin: 0,
  });
  slide.addText(period, {
    x: 9.5, y: 0.2, w: 3.5, h: 0.35,
    fontSize: 12, color: 'A0C4E8', fontFace: 'Arial', align: 'right', margin: 0,
  });
}

function addDisclaimer(slide, pptx) {
  slide.addText(DISCLAIMER, {
    x: 0.35, y: 0.8, w: 12.6, h: 0.28,
    fontSize: 9, color: COLORS.muted, fontFace: 'Arial', italic: true, margin: 0,
  });
}

function addFooter(slide, pptx, num) {
  slide.addText(`Report Intelligence  ·  ${num}`, {
    x: 0.35, y: 7.15, w: 12.6, h: 0.25,
    fontSize: 10, color: COLORS.muted, fontFace: 'Arial', align: 'right', margin: 0,
  });
}
