/**
 * Report Intelligence — GLP-1 calculation engine
 * Deterministic. Pure functions. Expects absolute counts.
 */

import { safeDivide, variationPct, share, sumField } from './common.js';

export function computeDemography(rows) {
  // rows: { dimension, value, visitasActual, usuariosActual, ... }
  const byDim = {};
  for (const r of rows) {
    const dim = r.dimension || 'Otros';
    if (!byDim[dim]) byDim[dim] = [];
    byDim[dim].push({
      value: r.value,
      visitasActual: r.visitasActual ?? 0,
      usuariosActual: r.usuariosActual ?? 0,
      atcActual: r.atcActual ?? r.addToCartActual ?? 0,
      recurrentesActual: r.recurrentesActual ?? 0,
      nuevosActual: r.nuevosActual ?? 0,
      visitasAnterior: r.visitasAnterior ?? 0,
      usuariosAnterior: r.usuariosAnterior ?? 0,
      atcAnterior: r.atcAnterior ?? r.addToCartAnterior ?? 0,
      deltaVisitas: variationPct(r.visitasActual, r.visitasAnterior),
    });
  }
  return byDim;
}

export function computeFunnel(funnelRows) {
  // funnelRows: [{ etapa, conteoActual, conteoAnterior }]
  const stages = funnelRows.map(r => ({
    etapa: r.etapa,
    actual: r.conteoActual ?? 0,
    anterior: r.conteoAnterior ?? 0,
    delta: variationPct(r.conteoActual, r.conteoAnterior),
  }));

  // Conversion rates relative to first stage
  const base = stages[0]?.actual || 0;
  return stages.map(s => ({
    ...s,
    conversionFromTop: safeDivide(s.actual, base),
  }));
}

export function computeByRegion(regionRows) {
  const totalMonto = sumField(regionRows, 'montoActual');
  return regionRows.map(r => ({
    region: r.region,
    montoActual: r.montoActual ?? 0,
    montoAnterior: r.montoAnterior ?? 0,
    deltaMonto: variationPct(r.montoActual, r.montoAnterior),
    pedidosActual: r.pedidosActual ?? 0,
    piezasActual: r.piezasActual ?? 0,
    pacientesActual: r.pacientesActual ?? 0,
    ticketActual: safeDivide(r.montoActual, r.pedidosActual),
    shareActual: share(r.montoActual, totalMonto),
    visitasActual: r.visitasActual ?? 0,
    usuariosActual: r.usuariosActual ?? 0,
  })).sort((a, b) => b.montoActual - a.montoActual);
}

export function computePaymentMethods(rows) {
  const total = sumField(rows, 'montoActual');
  return rows.map(r => ({
    formaPago: r.formaPago || r.nombre,
    montoActual: r.montoActual ?? 0,
    pedidosActual: r.pedidosActual ?? 0,
    ticketActual: safeDivide(r.montoActual, r.pedidosActual),
    shareActual: share(r.montoActual, total),
    deltaMonto: variationPct(r.montoActual, r.montoAnterior),
  })).sort((a, b) => b.montoActual - a.montoActual);
}

export function computeProducts(productRows) {
  const total = sumField(productRows, 'montoActual');
  return productRows
    .map(r => ({
      producto: r.producto || r.nombre,
      montoActual: r.montoActual ?? 0,
      montoAnterior: r.montoAnterior ?? 0,
      delta: (r.montoActual ?? 0) - (r.montoAnterior ?? 0),
      deltaPct: variationPct(r.montoActual, r.montoAnterior),
      pedidosActual: r.pedidosActual ?? 0,
      piezasActual: r.piezasActual ?? 0,
      pacientesActual: r.pacientesActual ?? 0,
      ticketActual: safeDivide(r.montoActual, r.pedidosActual),
      shareActual: share(r.montoActual, total),
    }))
    .sort((a, b) => b.montoActual - a.montoActual);
}

export function computeNegados(negadosRows) {
  const total = sumField(negadosRows, 'montoNegado');
  return {
    totalMonto: total,
    items: negadosRows
      .map(r => ({
        producto: r.producto || r.nombre,
        montoNegado: r.montoNegado ?? 0,
        pedidos: r.pedidos ?? 0,
        piezas: r.piezas ?? r.cantidad ?? 0,
        share: share(r.montoNegado, total),
      }))
      .sort((a, b) => b.montoNegado - a.montoNegado),
  };
}

export function computeTrafficSources(rows) {
  return rows.map(r => ({
    fuente: r.fuente || r.canal,
    visitasActual: r.visitasActual ?? 0,
    usuariosActual: r.usuariosActual ?? 0,
    atcActual: r.atcActual ?? r.addToCartActual ?? 0,
    deltaVisitas: variationPct(r.visitasActual, r.visitasAnterior),
    deltaAtc: variationPct(r.atcActual ?? r.addToCartActual, r.atcAnterior ?? r.addToCartAnterior),
  })).sort((a, b) => b.visitasActual - a.visitasActual);
}

/**
 * Build a simple summary for the results panel
 */
export function buildSummary({ demography, regions, products, negados, funnel }) {
  const summary = [];

  if (regions?.length) {
    const totalVenta = regions.reduce((s, r) => s + (r.montoActual || 0), 0);
    summary.push({ label: 'Venta total (regiones)', value: totalVenta });
  }
  if (products?.length) {
    summary.push({ label: 'Productos con venta', value: products.length });
    summary.push({ label: 'Top producto (monto)', value: products[0]?.montoActual ?? 0 });
  }
  if (negados?.totalMonto) {
    summary.push({ label: 'Monto negado total', value: negados.totalMonto });
  }
  if (funnel?.length) {
    const compra = funnel.find(f => f.etapa?.toLowerCase().includes('compra') && !f.etapa?.toLowerCase().includes('iniciar'));
    if (compra) summary.push({ label: 'Conversiones (compra)', value: compra.actual });
  }
  return summary;
}
