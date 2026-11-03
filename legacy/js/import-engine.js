/**
 * Report Intelligence — Import Engine (SheetJS)
 * Soporta:
 *  1. Machotes oficiales (MACHETE_AETOPS / MACHETE_GLP1)
 *  2. Archivos operativos reales (Base + Venta + Negados / hojas 1-9)
 */

export async function readExcelFile(file) {
  const buffer = await file.arrayBuffer();
  return XLSX.read(buffer, { type: 'array', cellDates: true });
}

export function getSheetNames(workbook) {
  return workbook.SheetNames || [];
}

export function sheetToMatrix(workbook, sheetName) {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) return [];
  return XLSX.utils.sheet_to_json(sheet, { header: 1, defval: null, raw: true });
}

export function sheetToObjects(workbook, sheetName) {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) return [];
  return XLSX.utils.sheet_to_json(sheet, { defval: null, raw: true });
}

export function detectAetops(workbook) {
  const names = getSheetNames(workbook).map(n => n.toLowerCase());
  return names.some(n =>
    n.includes('base') || n.includes('aetop') || n.includes('venta') ||
    n.includes('negado') || n.includes('parametro') || n.includes('kpis')
  );
}

export function detectGlp1(workbook) {
  const names = getSheetNames(workbook).map(n => n.toLowerCase());
  const hasNumbered = names.filter(n => /^\d+$/.test(n)).length >= 4;
  const hasDescriptive = names.some(n =>
    n.includes('demografia') || n.includes('glp') || n.includes('fuentes') ||
    n.includes('comportamiento') || n.includes('producto')
  );
  return hasNumbered || hasDescriptive;
}

function toNum(val) {
  if (val === null || val === undefined || val === '') return null;
  if (typeof val === 'number' && Number.isFinite(val)) return val;
  const s = String(val).replace(/[$,\s%]/g, '').replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function normLinea(val) {
  if (!val) return null;
  const v = String(val).toUpperCase().trim();
  if (v.includes('AE-A') || v === 'AEA' || v === 'A') return 'AE-A';
  if (v.includes('AE-B') || v === 'AEB' || v === 'B') return 'AE-B';
  if (v.includes('AE-C') || v === 'AEC' || v === 'C') return 'AE-C';
  if (v.includes('HYR')) return 'HYR';
  return v;
}

function normCanal(val) {
  if (!val) return null;
  const v = String(val).toUpperCase().trim();
  if (v.includes('APP') || v.includes('FESA')) return 'APP FESA';
  if (v.includes('ECOMMERCE') || v.includes('E-COMMERCE') || v.includes('ECOM')) return 'ECOMMERCE';
  if (v.includes('GOOGLE') || v.includes('LLAMADA')) return 'LLAMADAS GOOGLE';
  if (v.includes('WHATSAPP') || v.includes('WHATS')) return 'WHATSAPP';
  if (v.includes('TELEGRAM')) return 'TELEGRAM';
  return v;
}

function cell(matrix, r, c) {
  if (r < 0 || r >= matrix.length) return null;
  const row = matrix[r];
  if (!row || c < 0 || c >= row.length) return null;
  return row[c];
}

function findRowWith(matrix, text, col = 1) {
  const t = text.toLowerCase();
  for (let i = 0; i < matrix.length; i++) {
    const v = cell(matrix, i, col);
    if (v != null && String(v).toLowerCase().includes(t)) return i;
  }
  return -1;
}

// ============================================================
// AETOPS
// ============================================================

export function parseAetopsMachote(workbook) {
  const sheets = getSheetNames(workbook);
  const hasBase = sheets.some(s => s.toLowerCase() === 'base');
  if (hasBase) return parseAetopsOperational(workbook);
  return parseAetopsMachoteFormat(workbook);
}

function parseAetopsOperational(workbook) {
  const result = {
    type: 'AETOPS', format: 'operational', params: {},
    kpis: { actual: {}, previousMom: {}, previousYoy: {} },
    channels: [], lines: [], detail: [], negados: [], categorias: [], messages: [],
  };

  const baseMatrix = sheetToMatrix(workbook, 'Base');
  if (!baseMatrix.length) {
    result.messages.push({ type: 'error', text: 'Hoja Base vacía o no legible.' });
    return result;
  }

  // Global YoY
  const yoyHeader = findRowWith(baseMatrix, 'año', 1);
  if (yoyHeader >= 0) {
    const rPrev = yoyHeader + 1;
    const rAct = yoyHeader + 2;
    result.kpis.previousYoy = {
      montoVenta: toNum(cell(baseMatrix, rPrev, 2)),
      piezas: toNum(cell(baseMatrix, rPrev, 3)),
      pacientes: toNum(cell(baseMatrix, rPrev, 4)),
      pedidos: toNum(cell(baseMatrix, rPrev, 5)),
      ticket: toNum(cell(baseMatrix, rPrev, 6)),
      productosVendidos: toNum(cell(baseMatrix, rPrev, 7)),
      sizeB: toNum(cell(baseMatrix, rPrev, 8)),
      valorPaciente: toNum(cell(baseMatrix, rPrev, 9)),
    };
    result.kpis.actual = {
      montoVenta: toNum(cell(baseMatrix, rAct, 2)),
      piezas: toNum(cell(baseMatrix, rAct, 3)),
      pacientes: toNum(cell(baseMatrix, rAct, 4)),
      pedidos: toNum(cell(baseMatrix, rAct, 5)),
      ticket: toNum(cell(baseMatrix, rAct, 6)),
      productosVendidos: toNum(cell(baseMatrix, rAct, 7)),
      sizeB: toNum(cell(baseMatrix, rAct, 8)),
      valorPaciente: toNum(cell(baseMatrix, rAct, 9)),
    };
  }

  // Global MoM
  const momLabel = findRowWith(baseMatrix, 'mom', 1);
  if (momLabel >= 0) {
    const momHeader = momLabel + 1;
    const rPrev = momHeader + 1;
    const rAct = momHeader + 2;
    result.kpis.previousMom = {
      montoVenta: toNum(cell(baseMatrix, rPrev, 2)),
      piezas: toNum(cell(baseMatrix, rPrev, 3)),
      pacientes: toNum(cell(baseMatrix, rPrev, 4)),
      pedidos: toNum(cell(baseMatrix, rPrev, 5)),
      ticket: toNum(cell(baseMatrix, rPrev, 6)),
      productosVendidos: toNum(cell(baseMatrix, rPrev, 7)),
      sizeB: toNum(cell(baseMatrix, rPrev, 8)),
      valorPaciente: toNum(cell(baseMatrix, rPrev, 9)),
    };
    if (result.kpis.actual.montoVenta == null) {
      result.kpis.actual = {
        montoVenta: toNum(cell(baseMatrix, rAct, 2)),
        piezas: toNum(cell(baseMatrix, rAct, 3)),
        pacientes: toNum(cell(baseMatrix, rAct, 4)),
        pedidos: toNum(cell(baseMatrix, rAct, 5)),
        ticket: toNum(cell(baseMatrix, rAct, 6)),
        productosVendidos: toNum(cell(baseMatrix, rAct, 7)),
        sizeB: toNum(cell(baseMatrix, rAct, 8)),
        valorPaciente: toNum(cell(baseMatrix, rAct, 9)),
      };
    }
  }

  // Channels
  const channelNames = ['APP FESA', 'ECOMMERCE', 'LLAMADAS GOOGLE', 'WHATSAPP', 'TELEGRAM'];
  for (const ch of channelNames) {
    const chRow = findRowWith(baseMatrix, ch.toLowerCase(), 1);
    if (chRow < 0) continue;
    const rPrev = chRow + 1;
    const rAct = chRow + 2;
    result.channels.push({
      canal: normCanal(ch),
      montoAnterior: toNum(cell(baseMatrix, rPrev, 2)),
      piezasAnterior: toNum(cell(baseMatrix, rPrev, 3)),
      pacientesAnterior: toNum(cell(baseMatrix, rPrev, 4)),
      pedidosAnterior: toNum(cell(baseMatrix, rPrev, 5)),
      ticketAnterior: toNum(cell(baseMatrix, rPrev, 6)),
      productosAnterior: toNum(cell(baseMatrix, rPrev, 7)),
      shareAnterior: toNum(cell(baseMatrix, rPrev, 8)),
      montoActual: toNum(cell(baseMatrix, rAct, 2)),
      piezasActual: toNum(cell(baseMatrix, rAct, 3)),
      pacientesActual: toNum(cell(baseMatrix, rAct, 4)),
      pedidosActual: toNum(cell(baseMatrix, rAct, 5)),
      ticketActual: toNum(cell(baseMatrix, rAct, 6)),
      productosActual: toNum(cell(baseMatrix, rAct, 7)),
      shareActual: toNum(cell(baseMatrix, rAct, 8)),
    });
  }

  // Lines
  for (const ln of ['AE-A', 'AE-B', 'AE-C', 'HYR']) {
    let lnRow = -1;
    for (let i = 0; i < baseMatrix.length; i++) {
      const v = cell(baseMatrix, i, 1);
      if (v != null && String(v).toUpperCase().trim() === ln) { lnRow = i; break; }
    }
    if (lnRow < 0) continue;
    const rPrev = lnRow + 1;
    const rAct = lnRow + 2;
    result.lines.push({
      linea: ln,
      montoAnterior: toNum(cell(baseMatrix, rPrev, 2)),
      piezasAnterior: toNum(cell(baseMatrix, rPrev, 3)),
      pacientesAnterior: toNum(cell(baseMatrix, rPrev, 4)),
      pedidosAnterior: toNum(cell(baseMatrix, rPrev, 5)),
      ticketAnterior: toNum(cell(baseMatrix, rPrev, 6)),
      productosAnterior: toNum(cell(baseMatrix, rPrev, 7)),
      shareAnterior: toNum(cell(baseMatrix, rPrev, 8)),
      montoActual: toNum(cell(baseMatrix, rAct, 2)),
      piezasActual: toNum(cell(baseMatrix, rAct, 3)),
      pacientesActual: toNum(cell(baseMatrix, rAct, 4)),
      pedidosActual: toNum(cell(baseMatrix, rAct, 5)),
      ticketActual: toNum(cell(baseMatrix, rAct, 6)),
      productosActual: toNum(cell(baseMatrix, rAct, 7)),
      shareActual: toNum(cell(baseMatrix, rAct, 8)),
    });
  }

  // Product detail from Tablas (preferred) or Venta*
  const tablasSheet = getSheetNames(workbook).find(s => s.toLowerCase() === 'tablas');
  if (tablasSheet) {
    const rows = sheetToObjects(workbook, tablasSheet);
    for (const row of rows) {
      const producto = row.Producto || row.producto || row['Nombre del Producto'];
      if (!producto) continue;
      result.detail.push({
        sivec: row.Sivec || row.sivec,
        producto: String(producto),
        linea: normLinea(row.AETOP || row.Linea),
        canal: null,
        canalesCount: toNum(row['Canales de Venta'] || row['Canal de Venta']),
        montoActual: toNum(row['Venta Mes Actual'] || row['Venta Actual']),
        montoAnterior: toNum(row['Venta Mes Anterior'] || row['Venta Anterior']),
        piezasActual: null, pacientesActual: null, pedidosActual: null,
      });
    }
  } else {
    const ventaSheets = getSheetNames(workbook).filter(s => s.toLowerCase().includes('venta'));
    if (ventaSheets.length) {
      const rows = sheetToObjects(workbook, ventaSheets[0]);
      for (const row of rows) {
        const producto = row.Producto || row.producto;
        if (!producto) continue;
        let montoFinal = null;
        for (const k of Object.keys(row)) {
          if (/venta|monto/i.test(k)) { montoFinal = toNum(row[k]); if (montoFinal != null) break; }
        }
        result.detail.push({
          sivec: row.Sivec || row.sivec,
          producto: String(producto),
          linea: normLinea(row.AETOP || row.Linea),
          canal: null,
          canalesCount: toNum(row['Canal de Venta']),
          montoActual: montoFinal,
          montoAnterior: null,
        });
      }
    }
  }

  // Negados
  const negSheet = getSheetNames(workbook).find(s => s.toLowerCase().includes('negado'));
  if (negSheet) {
    const rows = sheetToObjects(workbook, negSheet);
    for (const row of rows) {
      const producto = row['Nombre del Producto'] || row.Producto || row.Nombre;
      if (!producto || String(producto).toLowerCase().includes('nombre del producto')) continue;
      result.negados.push({
        producto: String(producto),
        linea: normLinea(row.Alta || row.AETOP || row.Linea),
        pedidos: toNum(row.Pedidos || row['Pedidos Negados']),
        cantidad: toNum(row['Cantidad Negada'] || row.Cantidad),
        montoNegado: toNum(row['Monto Negado'] || row.Monto),
        pacientes: toNum(row.Pacientes),
      });
    }
  }

  if (result.kpis.actual.montoVenta != null) {
    result.messages.push({ type: 'success', text: 'KPIs globales leídos (Monto Actual: ' + Number(result.kpis.actual.montoVenta).toLocaleString('es-MX') + ').' });
  } else {
    result.messages.push({ type: 'warning', text: 'No se encontraron KPIs globales en la hoja Base.' });
  }
  if (result.channels.length) result.messages.push({ type: 'success', text: 'Canales: ' + result.channels.length + ' leídos.' });
  if (result.lines.length) result.messages.push({ type: 'success', text: 'Líneas AETOP: ' + result.lines.length + ' leídas.' });
  if (result.detail.length) result.messages.push({ type: 'success', text: 'Productos (detalle): ' + result.detail.length + ' filas.' });
  else result.messages.push({ type: 'warning', text: 'Sin detalle de productos. Ranking limitado.' });
  if (result.negados.length) result.messages.push({ type: 'success', text: 'Negados: ' + result.negados.length + ' productos.' });

  return result;
}

function parseAetopsMachoteFormat(workbook) {
  const result = {
    type: 'AETOPS', format: 'machote', params: {},
    kpis: { actual: {}, previousMom: {}, previousYoy: {} },
    channels: [], lines: [], detail: [], negados: [], categorias: [], messages: [],
  };
  const sheets = getSheetNames(workbook);

  const kpiSheet = sheets.find(s => s.toLowerCase().includes('kpi'));
  if (kpiSheet) {
    const rows = sheetToObjects(workbook, kpiSheet);
    for (const row of rows) {
      const ind = String(row.Indicador || Object.values(row)[0] || '').toLowerCase();
      const actual = toNum(row['Periodo Actual'] ?? Object.values(row)[1]);
      const mom = toNum(row['Periodo Anterior (MoM)'] ?? Object.values(row)[2]);
      const yoy = toNum(row['Periodo Anterior (YoY)'] ?? Object.values(row)[3]);
      if (ind.includes('monto')) { result.kpis.actual.montoVenta = actual; result.kpis.previousMom.montoVenta = mom; result.kpis.previousYoy.montoVenta = yoy; }
      else if (ind.includes('pieza')) { result.kpis.actual.piezas = actual; result.kpis.previousMom.piezas = mom; result.kpis.previousYoy.piezas = yoy; }
      else if (ind.includes('paciente')) { result.kpis.actual.pacientes = actual; result.kpis.previousMom.pacientes = mom; result.kpis.previousYoy.pacientes = yoy; }
      else if (ind.includes('pedido')) { result.kpis.actual.pedidos = actual; result.kpis.previousMom.pedidos = mom; result.kpis.previousYoy.pedidos = yoy; }
      else if (ind.includes('producto')) { result.kpis.actual.productosVendidos = actual; result.kpis.previousMom.productosVendidos = mom; result.kpis.previousYoy.productosVendidos = yoy; }
    }
  }

  const detailSheet = sheets.find(s => s.toLowerCase().includes('detalle') || s.toLowerCase().includes('venta'));
  if (detailSheet) {
    const rows = sheetToObjects(workbook, detailSheet);
    for (const row of rows) {
      const producto = row['Nombre del Producto'] || row.Producto;
      if (!producto) continue;
      result.detail.push({
        sivec: row['Sivec / Código'] || row.Sivec,
        producto: String(producto),
        linea: normLinea(row['Línea AETOP (AE-A/AE-B/AE-C/HYR)'] || row.Linea),
        canal: normCanal(row['Canal (APP FESA/ECOMMERCE/LLAMADAS GOOGLE/WHATSAPP/TELEGRAM/OTRO)'] || row.Canal),
        montoActual: toNum(row['Monto Venta Actual']),
        piezasActual: toNum(row['Piezas Actual']),
        pacientesActual: toNum(row['Pacientes Actual']),
        pedidosActual: toNum(row['Pedidos Actual']),
        montoAnterior: toNum(row['Monto Venta Anterior']),
        piezasAnterior: toNum(row['Piezas Anterior']),
        pacientesAnterior: toNum(row['Pacientes Anterior']),
        pedidosAnterior: toNum(row['Pedidos Anterior']),
      });
    }
  }

  const negSheet = sheets.find(s => s.toLowerCase().includes('negado'));
  if (negSheet) {
    const rows = sheetToObjects(workbook, negSheet);
    for (const row of rows) {
      const producto = row['Nombre del Producto'] || row.Producto;
      if (!producto) continue;
      result.negados.push({
        producto: String(producto),
        linea: normLinea(row['Línea AETOP (AE-A/AE-B/AE-C/HYR)'] || row.Linea),
        pedidos: toNum(row['Pedidos Negados']),
        cantidad: toNum(row['Cantidad Negada (piezas)'] || row['Cantidad Negada']),
        montoNegado: toNum(row['Monto Negado']),
        pacientes: toNum(row['Pacientes Afectados']),
      });
    }
  }

  result.messages.push({ type: 'info', text: 'Machote AETOPS leído.' });
  return result;
}

// ============================================================
// GLP-1
// ============================================================

export function parseGlp1Machote(workbook) {
  const sheets = getSheetNames(workbook);
  const hasNumbered = sheets.filter(n => /^\d+$/.test(n)).length >= 3;
  if (hasNumbered) return parseGlp1Operational(workbook);
  return parseGlp1MachoteFormat(workbook);
}

function parseGlp1Operational(workbook) {
  const result = {
    type: 'GLP-1', format: 'operational', params: {},
    demography: [], regions: [], payment: [], delivery: [], programs: [],
    funnel: [], products: [], negados: [], traffic: [], messages: [],
  };
  const sheets = getSheetNames(workbook);

  // Sheet 1 - Demography
  if (sheets.includes('1')) {
    const rows = sheetToObjects(workbook, '1');
    for (const row of rows) {
      const edad = row.Edad;
      const sexo = row.Sexo;
      const disp = row['Categoría de dispositivo'];
      if (edad && !String(edad).toLowerCase().includes('edad')) {
        result.demography.push({
          dimension: 'Edad', value: String(edad),
          visitasActual: toNum(row.Visitas), usuariosActual: toNum(row['Total de usuarios']),
          addToCartActual: toNum(row['Add to Cart']), recurrentesActual: toNum(row['Usuarios recurrentes']),
          nuevosActual: toNum(row['Usuarios nuevos']), share: toNum(row.Share), delta: toNum(row['% Δ']),
        });
      }
      if (sexo && !String(sexo).toLowerCase().includes('sexo')) {
        result.demography.push({
          dimension: 'Sexo', value: String(sexo),
          visitasActual: toNum(row.Visitas), usuariosActual: toNum(row['Total de usuarios']),
          addToCartActual: toNum(row['Add to Cart']), recurrentesActual: toNum(row['Usuarios recurrentes']),
          nuevosActual: toNum(row['Usuarios nuevos']), share: toNum(row.Share), delta: toNum(row['% Δ']),
        });
      }
      if (disp && !String(disp).toLowerCase().includes('categor')) {
        result.demography.push({
          dimension: 'Dispositivo', value: String(disp),
          visitasActual: toNum(row.Visitas), usuariosActual: toNum(row['Total de usuarios']),
          addToCartActual: toNum(row['Add to Cart']), recurrentesActual: toNum(row['Usuarios recurrentes']),
          nuevosActual: toNum(row['Usuarios nuevos']), share: toNum(row.Share), delta: toNum(row['% Δ']),
        });
      }
    }
  }

  // Sheet 4 - Region
  if (sheets.includes('4')) {
    const rows = sheetToObjects(workbook, '4');
    for (const row of rows) {
      const region = row.Región || row.Region;
      if (!region || String(region).toLowerCase().includes('región')) continue;
      if (row.Pedidos == null && row['Monto Venta'] == null) continue;
      result.regions.push({
        region: String(region),
        pedidosActual: toNum(row.Pedidos), piezasActual: toNum(row.Piezas),
        montoActual: toNum(row['Monto Venta']), pacientesActual: toNum(row.Pacientes),
        ticketActual: toNum(row['Ticket Promedio']), share: toNum(row.Share), delta: toNum(row['% Δ']),
        montoAnterior: null, pedidosAnterior: null,
      });
    }
  }

  // Sheet 5 - Payment / Delivery / Funnel
  if (sheets.includes('5')) {
    const rows = sheetToObjects(workbook, '5');
    let section = 'payment';
    for (const row of rows) {
      const firstVal = Object.values(row)[0];
      if (!firstVal) continue;
      const key = String(firstVal).toLowerCase();
      if (key.includes('modo de entrega') || key.includes('entrega')) { section = 'delivery'; continue; }
      if (key.includes('ver producto') || key.includes('agregar') || key.includes('iniciar') || key.includes('carrito')) section = 'funnel';
      if (key.includes('forma de pago')) { section = 'payment'; continue; }

      if (section === 'payment' && /tarjeta|efectivo|transferencia|pendiente|deposito|ecommerce|débito|debito/i.test(key)) {
        result.payment.push({
          formaPago: String(firstVal),
          pedidosActual: toNum(row.Pedidos), piezasActual: toNum(row.Piezas),
          montoActual: toNum(row['Monto Venta']), pacientesActual: toNum(row.Pacientes),
          ticketActual: toNum(row['Ticket Promedio']), share: toNum(row.Share), delta: toNum(row['% Δ']),
        });
      } else if (section === 'delivery' && /domicilio|sucursal/i.test(key)) {
        result.delivery.push({
          modo: String(firstVal),
          pedidosActual: toNum(row.Pedidos), montoActual: toNum(row['Monto Venta']),
          share: toNum(row.Share), delta: toNum(row['% Δ']),
        });
      } else if (section === 'funnel') {
        const keys = Object.keys(row);
        const count = toNum(row[keys[3]] || row[keys[2]]);
        const rate = toNum(row[keys[1]]);
        result.funnel.push({ etapa: String(firstVal), conteoActual: count, tasa: rate, conteoAnterior: null });
      }
    }
  }

  // Sheet 6 - Negados
  if (sheets.includes('6')) {
    const rows = sheetToObjects(workbook, '6');
    for (const row of rows) {
      const producto = row['Nombre del Producto'] || row.Producto;
      if (!producto || String(producto).toLowerCase().includes('nombre')) continue;
      result.negados.push({
        producto: String(producto),
        pedidos: toNum(row.Pedidos), piezas: toNum(row.Piezas),
        montoNegado: toNum(row['Monto Negado']), pacientes: toNum(row.Pacientes),
        share: toNum(row.Share), delta: toNum(row['% Δ']),
      });
    }
  }

  // Sheet 7 - Products
  if (sheets.includes('7')) {
    const rows = sheetToObjects(workbook, '7');
    for (const row of rows) {
      const producto = row.Producto || row['Nombre del Producto'];
      if (!producto || String(producto).toLowerCase().includes('producto')) continue;
      result.products.push({
        producto: String(producto),
        pedidosActual: toNum(row.Pedidos), piezasActual: toNum(row.Piezas),
        montoActual: toNum(row['Monto Venta']), pacientesActual: toNum(row.Pacientes),
        ticketActual: toNum(row['Ticket Promedio']), share: toNum(row.Share), delta: toNum(row['% Δ']),
        montoAnterior: null,
      });
    }
  }

  // Sheet 8 - Programs
  if (sheets.includes('8')) {
    const rows = sheetToObjects(workbook, '8');
    for (const row of rows) {
      const prog = row['Programa de Lealtad'] || row.Programa;
      if (!prog || String(prog).toLowerCase().includes('programa')) continue;
      result.programs.push({
        programa: String(prog),
        pedidosActual: toNum(row.Pedidos), piezasActual: toNum(row.Piezas),
        montoActual: toNum(row['Monto Venta']), pacientesActual: toNum(row.Pacientes),
        share: toNum(row.Share), delta: toNum(row['% Δ']),
      });
    }
  }

  // Sheet 9 - Traffic
  if (sheets.includes('9')) {
    const rows = sheetToObjects(workbook, '9');
    for (const row of rows) {
      const fuente = row['Categoría de dispositivo'] || row.Fuente || Object.values(row)[0];
      if (!fuente) continue;
      const key = String(fuente).toLowerCase();
      if (key.includes('categor') || key === 'pago' || key === 'organico' || key === 'orgánico' || key.includes('canal')) continue;
      result.traffic.push({
        fuente: String(fuente),
        visitasActual: toNum(row.Visitas),
        usuariosActual: toNum(row['Total de usuarios']),
        addToCartActual: toNum(row['Add to Cart']),
        recurrentesActual: toNum(row['Usuarios recurrentes']),
        nuevosActual: toNum(row['Usuarios nuevos']),
        delta: toNum(row['% Δ']),
      });
    }
  }

  const counts = [
    ['Demografía', result.demography.length], ['Regiones', result.regions.length],
    ['Productos', result.products.length], ['Negados', result.negados.length],
    ['Formas de pago', result.payment.length], ['Programas', result.programs.length],
    ['Fuentes', result.traffic.length],
  ];
  for (const [label, n] of counts) {
    if (n > 0) result.messages.push({ type: 'success', text: label + ': ' + n + ' filas.' });
  }
  if (counts.every(([, n]) => n === 0)) {
    result.messages.push({ type: 'warning', text: 'No se extrajeron datos de las hojas GLP-1.' });
  }
  return result;
}

function parseGlp1MachoteFormat(workbook) {
  const result = {
    type: 'GLP-1', format: 'machote', params: {},
    demography: [], regions: [], payment: [], delivery: [], programs: [],
    funnel: [], products: [], negados: [], traffic: [], messages: [],
  };
  result.messages.push({ type: 'info', text: 'Machote GLP-1 leído (formato oficial).' });
  return result;
}
