/**
 * Report Intelligence — Common calculation utilities
 * All functions are pure and deterministic.
 */

export function safeDivide(numerator, denominator) {
  if (denominator === null || denominator === undefined || denominator === 0) return null;
  if (numerator === null || numerator === undefined) return null;
  return numerator / denominator;
}

export function variationPct(actual, previous) {
  if (previous === null || previous === undefined || previous === 0) {
    if (actual === 0 || actual === null) return 0;
    return null; // cannot compute meaningful % from zero base
  }
  if (actual === null || actual === undefined) return null;
  return (actual - previous) / previous;
}

export function share(part, total) {
  return safeDivide(part, total);
}

export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return Number(value).toLocaleString('es-MX', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const pct = value * 100;
  const sign = pct > 0 ? '+' : '';
  return sign + pct.toFixed(0) + '%';
}

/**
 * Ranking hybrid rule:
 * - Exclude products with actual=0 AND previous=0
 * - Take products that accumulate 80% of current sales
 * - Max 15 items, min 8 items
 * - Keep ties
 */
export function rankProducts(items, options = {}) {
  const {
    valueKey = 'delta',
    salesKey = 'actual',
    threshold = 0.8,
    maxItems = 15,
    minItems = 8,
    direction = 'desc', // 'desc' = growth, 'asc' = decline
  } = options;

  // Filter out zero-zero
  let filtered = items.filter(item => {
    const a = item[salesKey] ?? 0;
    const p = item.previous ?? 0;
    return !(a === 0 && p === 0);
  });

  // Sort
  filtered.sort((a, b) => {
    const va = a[valueKey] ?? 0;
    const vb = b[valueKey] ?? 0;
    if (direction === 'desc') {
      if (vb !== va) return vb - va;
      return (b[salesKey] ?? 0) - (a[salesKey] ?? 0); // tie-break by sales
    }
    if (va !== vb) return va - vb;
    return (b[salesKey] ?? 0) - (a[salesKey] ?? 0);
  });

  // 80% cumulative of current sales
  const totalSales = filtered.reduce((s, i) => s + (i[salesKey] ?? 0), 0);
  let cumulative = 0;
  let result = [];

  for (const item of filtered) {
    result.push(item);
    cumulative += item[salesKey] ?? 0;
    if (totalSales > 0 && cumulative / totalSales >= threshold && result.length >= minItems) {
      break;
    }
    if (result.length >= maxItems) break;
  }

  // Ensure minimum
  if (result.length < minItems) {
    result = filtered.slice(0, Math.min(minItems, filtered.length));
  }

  // Cap at max
  if (result.length > maxItems) {
    result = result.slice(0, maxItems);
  }

  return result;
}

export function sumField(rows, field) {
  return rows.reduce((acc, r) => acc + (Number(r[field]) || 0), 0);
}
