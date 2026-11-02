/**
 * Report Intelligence — AETOPS calculation engine
 * Deterministic. Pure functions.
 */

import {
  safeDivide,
  variationPct,
  share,
  rankProducts,
  sumField,
} from './common.js';

/**
 * Core KPIs from global totals
 */
export function computeGlobalKpis(actual, previous) {
  const montoActual = actual.montoVenta ?? null;
  const montoPrev = previous?.montoVenta ?? null;
  const piezasActual = actual.piezas ?? null;
  const piezasPrev = previous?.piezas ?? null;
  const pacientesActual = actual.pacientes ?? null;
  const pacientesPrev = previous?.pacientes ?? null;
  const pedidosActual = actual.pedidos ?? null;
  const pedidosPrev = previous?.pedidos ?? null;
  const productosActual = actual.productosVendidos ?? null;
  const productosPrev = previous?.productosVendidos ?? null;

  const sizeB = safeDivide(piezasActual, pacientesActual);
  const sizeBPrev = safeDivide(piezasPrev, pacientesPrev);
  const valorPaciente = safeDivide(montoActual, pacientesActual);
  const valorPacientePrev = safeDivide(montoPrev, pacientesPrev);
  const ticket = safeDivide(montoActual, pedidosActual);
  const ticketPrev = safeDivide(montoPrev, pedidosPrev);

  const kpis = [
    {
      name: 'Monto Venta',
      actual: montoActual,
      previous: montoPrev,
      delta: variationPct(montoActual, montoPrev),
    },
    {
      name: 'Piezas',
      actual: piezasActual,
      previous: piezasPrev,
      delta: variationPct(piezasActual, piezasPrev),
    },
    {
      name: 'Pacientes',
      actual: pacientesActual,
      previous: pacientesPrev,
      delta: variationPct(pacientesActual, pacientesPrev),
    },
    {
      name: 'Pedidos',
      actual: pedidosActual,
      previous: pedidosPrev,
      delta: variationPct(pedidosActual, pedidosPrev),
    },
    {
      name: 'Productos Vendidos',
      actual: productosActual,
      previous: productosPrev,
      delta: variationPct(productosActual, productosPrev),
    },
    {
      name: 'Ticket Promedio',
      actual: ticket,
      previous: ticketPrev,
      delta: variationPct(ticket, ticketPrev),
    },
    {
      name: 'Size B',
      actual: sizeB,
      previous: sizeBPrev,
      delta: variationPct(sizeB, sizeBPrev),
    },
    {
      name: 'V. Paciente',
      actual: valorPaciente,
      previous: valorPacientePrev,
      delta: variationPct(valorPaciente, valorPacientePrev),
    },
  ];

  return {
    kpis,
    sizeB,
    valorPaciente,
    ticket,
  };
}

/**
 * Aggregate by line (AE-A, AE-B, AE-C, HYR)
 * Expects detail rows with: linea, montoActual, montoAnterior, piezasActual, ...
 */
export function computeByLine(detailRows) {
  const lines = ['AE-A', 'AE-B', 'AE-C', 'HYR'];
  const totalActual = sumField(detailRows, 'montoActual');
  const totalPrev = sumField(detailRows, 'montoAnterior');

  return lines.map(linea => {
    const rows = detailRows.filter(r => (r.linea || '').toUpperCase() === linea);
    const montoActual = sumField(rows, 'montoActual');
    const montoAnterior = sumField(rows, 'montoAnterior');
    const piezasActual = sumField(rows, 'piezasActual');
    const piezasAnterior = sumField(rows, 'piezasAnterior');
    const pacientesActual = sumField(rows, 'pacientesActual');
    const pacientesAnterior = sumField(rows, 'pacientesAnterior');
    const pedidosActual = sumField(rows, 'pedidosActual');
    const pedidosAnterior = sumField(rows, 'pedidosAnterior');

    return {
      linea,
      montoActual,
      montoAnterior,
      deltaMonto: variationPct(montoActual, montoAnterior),
      piezasActual,
      piezasAnterior,
      deltaPiezas: variationPct(piezasActual, piezasAnterior),
      pacientesActual,
      pacientesAnterior,
      deltaPacientes: variationPct(pacientesActual, pacientesAnterior),
      pedidosActual,
      pedidosAnterior,
      deltaPedidos: variationPct(pedidosActual, pedidosAnterior),
      ticketActual: safeDivide(montoActual, pedidosActual),
      ticketAnterior: safeDivide(montoAnterior, pedidosAnterior),
      shareActual: share(montoActual, totalActual),
      shareAnterior: share(montoAnterior, totalPrev),
    };
  });
}

/**
 * Aggregate by channel
 */
export function computeByChannel(detailRows) {
  const channels = [...new Set(detailRows.map(r => r.canal).filter(Boolean))];
  const totalActual = sumField(detailRows, 'montoActual');
  const totalPrev = sumField(detailRows, 'montoAnterior');

  return channels.map(canal => {
    const rows = detailRows.filter(r => r.canal === canal);
    const montoActual = sumField(rows, 'montoActual');
    const montoAnterior = sumField(rows, 'montoAnterior');

    return {
      canal,
      montoActual,
      montoAnterior,
      deltaMonto: variationPct(montoActual, montoAnterior),
      piezasActual: sumField(rows, 'piezasActual'),
      piezasAnterior: sumField(rows, 'piezasAnterior'),
      pacientesActual: sumField(rows, 'pacientesActual'),
      pacientesAnterior: sumField(rows, 'pacientesAnterior'),
      pedidosActual: sumField(rows, 'pedidosActual'),
      pedidosAnterior: sumField(rows, 'pedidosAnterior'),
      shareActual: share(montoActual, totalActual),
      shareAnterior: share(montoAnterior, totalPrev),
    };
  }).sort((a, b) => (b.montoActual || 0) - (a.montoActual || 0));
}

/**
 * Product ranking (growth / decline)
 * Expects rows aggregated by product (sum across channels)
 */
export function computeProductRanking(detailRows) {
  // Aggregate by product
  const byProduct = {};
  for (const r of detailRows) {
    const key = r.producto || r.nombreProducto || 'SIN NOMBRE';
    if (!byProduct[key]) {
      byProduct[key] = {
        producto: key,
        linea: r.linea,
        actual: 0,
        previous: 0,
        canales: new Set(),
      };
    }
    byProduct[key].actual += Number(r.montoActual) || 0;
    byProduct[key].previous += Number(r.montoAnterior) || 0;
    if (r.canal) byProduct[key].canales.add(r.canal);
  }

  const items = Object.values(byProduct).map(p => ({
    ...p,
    delta: (p.actual || 0) - (p.previous || 0),
    canalesCount: p.canales.size,
    canales: undefined,
  }));

  const growth = rankProducts(items, {
    valueKey: 'delta',
    salesKey: 'actual',
    direction: 'desc',
  });

  const decline = rankProducts(items, {
    valueKey: 'delta',
    salesKey: 'actual',
    direction: 'asc',
  });

  return { growth, decline, all: items };
}

/**
 * Causas de la caída (when product × channel detail is available)
 * Categories: Producto no vendido | Menos pacientes | Menos piezas por paciente | Ticket menor | Residual
 */
export function computeCausasCaida(detailRows, targetChannels = ['WHATSAPP', 'LLAMADAS GOOGLE']) {
  const results = [];

  for (const canal of targetChannels) {
    const rows = detailRows.filter(r =>
      (r.canal || '').toUpperCase().includes(canal.toUpperCase().replace('LLAMADAS ', ''))
      || (r.canal || '').toUpperCase() === canal.toUpperCase()
    );

    let noVendido = 0;
    let residual = 0;
    let countNoVendido = 0;

    for (const r of rows) {
      const actual = Number(r.montoActual) || 0;
      const prev = Number(r.montoAnterior) || 0;
      const delta = actual - prev;

      if (actual === 0 && prev > 0) {
        noVendido += delta; // negative
        countNoVendido += 1;
      } else {
        residual += delta;
      }
    }

    const totalDelta = noVendido + residual;
    if (totalDelta >= 0) continue; // only care about declines for this section

    results.push({
      canal,
      totalDelta,
      productoNoVendido: noVendido,
      countProductosNoVendidos: countNoVendido,
      residual,
      // Future: when patient/piece detail per product×channel is available,
      // we can split residual into "menos pacientes", "menos piezas", "ticket menor"
    });
  }

  return results;
}

/**
 * Negados summary
 */
export function computeNegados(negadosRows) {
  const totalMonto = sumField(negadosRows, 'montoNegado');
  const byLine = {};

  for (const r of negadosRows) {
    const linea = r.linea || 'SIN LÍNEA';
    if (!byLine[linea]) byLine[linea] = { linea, monto: 0, pedidos: 0, cantidad: 0 };
    byLine[linea].monto += Number(r.montoNegado) || 0;
    byLine[linea].pedidos += Number(r.pedidos) || 0;
    byLine[linea].cantidad += Number(r.cantidad) || 0;
  }

  const lines = Object.values(byLine).map(l => ({
    ...l,
    share: share(l.monto, totalMonto),
  })).sort((a, b) => b.monto - a.monto);

  const topProducts = [...negadosRows]
    .sort((a, b) => (b.montoNegado || 0) - (a.montoNegado || 0))
    .slice(0, 10)
    .map(r => ({
      producto: r.producto || r.nombre,
      linea: r.linea,
      montoNegado: r.montoNegado,
      pedidos: r.pedidos,
      cantidad: r.cantidad,
      share: share(r.montoNegado, totalMonto),
    }));

  return { totalMonto, lines, topProducts };
}
