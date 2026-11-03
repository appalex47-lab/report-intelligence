/**
 * Report Intelligence — Main application (Alpine.js)
 */

import { readExcelFile, detectAetops, detectGlp1, parseAetopsMachote, parseGlp1Machote, getSheetNames } from './import-engine.js';
import { computeGlobalKpis, computeByLine, computeByChannel, computeProductRanking, computeCausasCaida, computeNegados as computeNegadosAetops } from './calculations/aetops.js';
import { computeByRegion, computeProducts, computeNegados as computeNegadosGlp1, computeFunnel, computePaymentMethods, buildSummary } from './calculations/glp1.js';
import { formatNumber, formatPct } from './calculations/common.js';
import { generateAetopsPptx } from './generators/pptx-aetops.js';
import { generateGlp1Pptx } from './generators/pptx-glp1.js';

const HISTORY_KEY = 'report_intelligence_history';

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(list) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
}

window.reportApp = function reportApp() {
  return {
    view: 'dashboard',
    step: 1,
    dragOver: false,
    processing: false,
    generating: false,

    config: {
      businessUnit: '',
      periodicity: '',
      year: new Date().getFullYear(),
      periodLabel: '',
    },

    files: [],
    validation: null,
    results: null,
    history: loadHistory(),

    get canGoToStep2() {
      return this.config.businessUnit && this.config.periodicity && this.config.periodLabel;
    },

    formatNumber,
    formatPct,

    formatSize(bytes) {
      if (bytes < 1024) return bytes + ' B';
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    handleDrop(event) {
      this.dragOver = false;
      const fileList = event.dataTransfer?.files;
      if (fileList) this.addFiles(fileList);
    },

    handleFiles(event) {
      const fileList = event.target.files;
      if (fileList) this.addFiles(fileList);
      event.target.value = '';
    },

    addFiles(fileList) {
      for (const f of fileList) {
        if (!f.name.match(/\.xlsx?$/i)) continue;
        if (this.files.some(x => x.name === f.name && x.size === f.size)) continue;
        this.files.push(f);
      }
    },

    removeFile(idx) {
      this.files.splice(idx, 1);
    },

    async processFiles() {
      if (this.files.length === 0) return;
      this.processing = true;
      this.validation = null;
      this.results = null;

      const messages = [];
      let filesProcessed = 0;
      let sheetsRecognized = 0;
      let indicatorsOk = 0;
      let warnings = 0;
      let hasBlockingErrors = false;

      let aetopsData = null;
      let glp1Data = null;

      try {
        for (const file of this.files) {
          const wb = await readExcelFile(file);
          const names = getSheetNames(wb);
          sheetsRecognized += names.length;
          filesProcessed += 1;

          const isAetops = detectAetops(wb) || this.config.businessUnit === 'AETOPS';
          const isGlp1 = detectGlp1(wb) || this.config.businessUnit === 'GLP-1';

          if (this.config.businessUnit === 'AETOPS' && isAetops) {
            aetopsData = parseAetopsMachote(wb);
            messages.push(...(aetopsData.messages || []));
          } else if (this.config.businessUnit === 'GLP-1' && isGlp1) {
            glp1Data = parseGlp1Machote(wb);
            messages.push(...(glp1Data.messages || []));
          } else {
            messages.push({
              type: 'warning',
              text: `El archivo "${file.name}" no coincide claramente con la unidad de negocio seleccionada (${this.config.businessUnit}).`,
            });
            warnings += 1;
          }
        }

        // Run calculations
        if (this.config.businessUnit === 'AETOPS' && aetopsData) {
          const prev = aetopsData.kpis.previousMom?.montoVenta != null
            ? aetopsData.kpis.previousMom
            : aetopsData.kpis.previousYoy;

          const global = computeGlobalKpis(aetopsData.kpis.actual, prev);
          indicatorsOk += global.kpis.filter(k => k.actual != null).length;

          // Prefer pre-parsed lines/channels from Base sheet when available
          let byLine = [];
          if (aetopsData.lines && aetopsData.lines.length) {
            byLine = aetopsData.lines.map(l => ({
              linea: l.linea,
              montoActual: l.montoActual,
              montoAnterior: l.montoAnterior,
              deltaMonto: l.montoAnterior ? (l.montoActual - l.montoAnterior) / l.montoAnterior : null,
              piezasActual: l.piezasActual,
              pacientesActual: l.pacientesActual,
              pedidosActual: l.pedidosActual,
              shareActual: l.shareActual,
            }));
          } else if (aetopsData.detail.length) {
            byLine = computeByLine(aetopsData.detail);
          }

          let byChannel = [];
          if (aetopsData.channels && aetopsData.channels.length) {
            byChannel = aetopsData.channels.map(c => ({
              canal: c.canal,
              montoActual: c.montoActual,
              montoAnterior: c.montoAnterior,
              deltaMonto: c.montoAnterior ? (c.montoActual - c.montoAnterior) / c.montoAnterior : null,
              piezasActual: c.piezasActual,
              pacientesActual: c.pacientesActual,
              pedidosActual: c.pedidosActual,
              shareActual: c.shareActual,
            }));
          } else if (aetopsData.detail.length) {
            byChannel = computeByChannel(aetopsData.detail);
          }

          const ranking = aetopsData.detail.length ? computeProductRanking(aetopsData.detail) : { growth: [], decline: [] };
          const causas = aetopsData.detail.length ? computeCausasCaida(aetopsData.detail) : [];
          const negados = aetopsData.negados.length ? computeNegadosAetops(aetopsData.negados) : null;

          this.results = {
            aetops: {
              ...global,
              byLine,
              byChannel,
              ranking,
              causas,
              negados,
              raw: aetopsData,
            },
          };

          messages.push(...(aetopsData.messages || []));
          if (aetopsData.detail.length === 0) {
            messages.push({ type: 'warning', text: 'No hay detalle de productos. Ranking limitado.' });
            warnings += 1;
          }
        }

        if (this.config.businessUnit === 'GLP-1' && glp1Data) {
          const regions = glp1Data.regions.length ? computeByRegion(glp1Data.regions) : [];
          const products = glp1Data.products.length ? computeProducts(glp1Data.products) : [];
          const negados = glp1Data.negados.length ? computeNegadosGlp1(glp1Data.negados) : null;
          const funnel = glp1Data.funnel.length ? computeFunnel(glp1Data.funnel) : [];
          const payment = glp1Data.payment.length ? computePaymentMethods(glp1Data.payment) : [];
          const summary = buildSummary({ regions, products, negados, funnel });

          indicatorsOk += summary.length + products.length;

          this.results = {
            glp1: {
              summary,
              regions,
              products,
              negados,
              funnel,
              payment,
              raw: glp1Data,
            },
          };

          messages.push({ type: 'success', text: `GLP-1 procesado: ${regions.length} regiones, ${products.length} productos.` });
        }

        if (!this.results) {
          hasBlockingErrors = true;
          messages.push({ type: 'error', text: 'No se pudo extraer información útil de los archivos cargados.' });
        }

        this.validation = {
          filesProcessed,
          sheetsRecognized,
          indicatorsOk,
          warnings: warnings + messages.filter(m => m.type === 'warning').length,
          hasBlockingErrors,
          messages,
        };

        this.step = 3;
      } catch (err) {
        console.error(err);
        this.validation = {
          filesProcessed,
          sheetsRecognized,
          indicatorsOk: 0,
          warnings: 0,
          hasBlockingErrors: true,
          messages: [{ type: 'error', text: 'Error al procesar archivos: ' + (err.message || String(err)) }],
        };
        this.step = 3;
      } finally {
        this.processing = false;
      }
    },


    async generatePptx() {
      if (!this.results) return;
      this.generating = true;
      try {
        if (this.config.businessUnit === 'AETOPS' && this.results.aetops) {
          await generateAetopsPptx(this.results.aetops, this.config);
        } else if (this.config.businessUnit === 'GLP-1' && this.results.glp1) {
          await generateGlp1Pptx(this.results.glp1, this.config);
        } else {
          alert('No hay resultados para generar la presentación.');
          return;
        }
        this.saveToHistory();
      } catch (err) {
        console.error(err);
        alert('Error al generar PPTX: ' + (err.message || String(err)));
      } finally {
        this.generating = false;
      }
    },

    saveToHistory() {
      const entry = {
        businessUnit: this.config.businessUnit,
        periodicity: this.config.periodicity,
        periodLabel: this.config.periodLabel,
        year: this.config.year,
        generatedAt: new Date().toLocaleString('es-MX'),
        status: 'ok',
      };
      this.history.unshift(entry);
      if (this.history.length > 50) this.history = this.history.slice(0, 50);
      saveHistory(this.history);
      alert('Reporte guardado en el historial local.');
    },

    removeFromHistory(idx) {
      this.history.splice(idx, 1);
      saveHistory(this.history);
    },
  };
};
