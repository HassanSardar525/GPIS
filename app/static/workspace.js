/* Page navigation and source-backed charts. Loaded before app.js. */
let workspaceReady = false;
let factComparisonRequest = 0;
const censusRequests = new Map();

function censusData(metric) {
  if (!censusRequests.has(metric)) {
    const request = json(`/api/v1/census-rankings?metric=${encodeURIComponent(metric)}`)
      .catch(error => { censusRequests.delete(metric); throw error; });
    censusRequests.set(metric, request);
  }
  return censusRequests.get(metric);
}

function navigateWorkspace(loadSelection = true) {
  const parts = location.hash.split('?')[0].split('/');
  const page = ['overview', 'district', 'compare', 'about'].includes(parts[1]) ? parts[1] : 'overview';
  document.querySelectorAll('[data-page]').forEach(element => { element.hidden = element.dataset.page !== page; });
  document.querySelectorAll('[data-nav]').forEach(link => {
    if (link.dataset.nav === page) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  document.title = `${page === 'district' ? 'District Profile & Ask GPIS' : page === 'compare' ? 'Compare' : page === 'about' ? 'About GPIS' : 'Explore'} · GPIS`;
  if (loadSelection && page === 'district' && parts[2] && parts[2] !== state.district?.slug) {
    if (state.districts.some(item => item.slug === parts[2])) {
      select.value = parts[2];
      loadDistrict(parts[2]).catch(showDistrictError);
    } else {
      setBusy(document.querySelector('#notice'), false, 'That district is not available. Choose a district from the list.');
    }
  }
  if (page === 'compare' && state.district) {
    loadFactComparison();
    loadRankings().catch(showRankingError);
  }
}

window.addEventListener('hashchange', () => navigateWorkspace(workspaceReady));
document.addEventListener('DOMContentLoaded', () => navigateWorkspace(false));

function initWorkspaceNavigation() {
  const other = document.querySelector('#compare-other');
  other.innerHTML = state.districts.map(item => `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)}</option>`).join('');
  other.value = state.districts.find(item => item.slug !== select.value)?.slug || select.value;
  if (!workspaceReady) {
    other.addEventListener('change', loadFactComparison);
    document.querySelector('#fact-comparison').addEventListener('click', event => {
      if (event.target.closest('[data-action="retry-facts"]')) loadFactComparison();
    });
    workspaceReady = true;
  }
  if (!location.hash) history.replaceState(null, '', '#/overview');
  navigateWorkspace(false);
}

function syncWorkspaceDistrict(data) {
  const profile = '#/district/' + data.slug;
  document.querySelector('#open-profile').href = profile;
  document.querySelector('[data-nav="district"]').href = profile;
  if (location.hash.startsWith('#/district')) history.replaceState(null, '', profile + (location.hash.includes('?') ? '?' + location.hash.split('?')[1] : ''));
  if (location.hash.startsWith('#/compare')) loadFactComparison();
}

function renderComparisonCharts(datasets, left, right) {
  const getMetric = (key) => datasets.find(d => d.metric === key);
  const dsTotalLit = getMetric('literacy_total_pct');
  const dsMaleLit = getMetric('literacy_male_pct');
  const dsFemaleLit = getMetric('literacy_female_pct');

  const lTotalLit = dsTotalLit?.rows.find(r => r.slug === left.slug)?.value;
  const rTotalLit = dsTotalLit?.rows.find(r => r.slug === right.slug)?.value;
  const lMaleLit = dsMaleLit?.rows.find(r => r.slug === left.slug)?.value;
  const rMaleLit = dsMaleLit?.rows.find(r => r.slug === right.slug)?.value;
  const lFemaleLit = dsFemaleLit?.rows.find(r => r.slug === left.slug)?.value;
  const rFemaleLit = dsFemaleLit?.rows.find(r => r.slug === right.slug)?.value;

  const radius = 38;
  const circumference = 2 * Math.PI * radius; // ~238.76
  const makeDonut = (districtName, val, maleVal, femaleVal, colorClass, isLeft) => {
    const pct = val != null ? Math.max(0, Math.min(100, val)) : 0;
    const offset = Math.max(0, circumference - (pct / 100) * circumference);
    return `<div class="comp-donut-card ${colorClass}">
      <div class="comp-donut-head">
        <span class="comp-donut-badge ${isLeft ? 'badge-primary' : 'badge-compare'}">${isLeft ? 'Primary District' : 'Comparison District'}</span>
        <h4 class="comp-donut-name">${escapeHtml(districtName)}</h4>
      </div>
      <div class="comp-donut-meter-wrap" aria-hidden="true">
        <svg class="comp-donut-svg" viewBox="0 0 96 96" width="96" height="96">
          <circle class="comp-donut-track" cx="48" cy="48" r="${radius}" />
          <circle class="comp-donut-arc arc-${colorClass}" cx="48" cy="48" r="${radius}" style="stroke-dasharray: ${circumference}; stroke-dashoffset: ${offset};" />
        </svg>
        <div class="comp-donut-center">
          <strong>${val != null ? number(val, 1) + '%' : '—'}</strong>
          <small>Total Literacy</small>
        </div>
      </div>
      <div class="comp-donut-substats">
        <span class="substat">Male: <strong>${maleVal != null ? number(maleVal, 1) + '%' : '—'}</strong></span>
        <span class="substat-sep">·</span>
        <span class="substat">Female: <strong>${femaleVal != null ? number(femaleVal, 1) + '%' : '—'}</strong></span>
      </div>
    </div>`;
  };

  const leftDonut = makeDonut(left.name, lTotalLit, lMaleLit, lFemaleLit, 'left-district', true);
  const rightDonut = makeDonut(right.name, rTotalLit, rMaleLit, rFemaleLit, 'right-district', false);

  const barCards = datasets.map(dataset => {
    const lRow = dataset.rows.find(r => r.slug === left.slug);
    const rRow = dataset.rows.find(r => r.slug === right.slug);
    const lVal = lRow ? lRow.value : null;
    const rVal = rRow ? rRow.value : null;
    const maxVal = Math.max(lVal || 0, rVal || 0, 1);
    const lPct = lVal != null ? Math.max(4, Math.min(100, Math.round((lVal / maxVal) * 100))) : 0;
    const rPct = rVal != null ? Math.max(4, Math.min(100, Math.round((rVal / maxVal) * 100))) : 0;

    let deltaHtml = '';
    if (lVal != null && rVal != null) {
      const diff = lVal - rVal;
      if (dataset.unit === 'percent') {
        const diffAbs = Math.abs(diff).toFixed(1);
        if (diff > 0.05) {
          deltaHtml = `<span class="comp-delta-badge lead-left">${escapeHtml(left.name)} +${diffAbs} pp</span>`;
        } else if (diff < -0.05) {
          deltaHtml = `<span class="comp-delta-badge lead-right">${escapeHtml(right.name)} +${diffAbs} pp</span>`;
        } else {
          deltaHtml = `<span class="comp-delta-badge lead-equal">Equal (±0 pp)</span>`;
        }
      } else {
        const diffAbs = Math.abs(diff);
        if (diff > 0) {
          deltaHtml = `<span class="comp-delta-badge lead-left">${escapeHtml(left.name)} +${number(diffAbs)}</span>`;
        } else if (diff < 0) {
          deltaHtml = `<span class="comp-delta-badge lead-right">${escapeHtml(right.name)} +${number(diffAbs)}</span>`;
        } else {
          deltaHtml = `<span class="comp-delta-badge lead-equal">Equal</span>`;
        }
      }
    }

    const formatVal = val => val == null ? 'Unavailable' : `${number(val, dataset.unit === 'percent' ? 2 : 0)}${dataset.unit === 'percent' ? '%' : ''}`;

    return `<div class="comp-bar-card">
      <div class="comp-bar-head">
        <span class="comp-bar-title">${escapeHtml(dataset.label)}</span>
        ${deltaHtml}
      </div>
      <div class="comp-bars-body">
        <div class="comp-bar-row">
          <span class="comp-bar-name" title="${escapeHtml(left.name)}">${escapeHtml(left.name)}</span>
          <div class="comp-bar-track">
            <div class="comp-bar-fill fill-left" style="width: ${lPct}%;"></div>
          </div>
          <span class="comp-bar-value">${escapeHtml(formatVal(lVal))}</span>
        </div>
        <div class="comp-bar-row">
          <span class="comp-bar-name" title="${escapeHtml(right.name)}">${escapeHtml(right.name)}</span>
          <div class="comp-bar-track">
            <div class="comp-bar-fill fill-right" style="width: ${rPct}%;"></div>
          </div>
          <span class="comp-bar-value">${escapeHtml(formatVal(rVal))}</span>
        </div>
      </div>
    </div>`;
  }).join('');

  return `<div class="comparison-visual-section">
    <div class="comparison-donuts-header">
      <h3 class="comparison-visual-heading">Literacy Rate Comparison (Census 2023)</h3>
      <p class="comparison-visual-sub">Side-by-side literacy breakdown with male and female parity</p>
    </div>
    <div class="comparison-donuts-grid">
      ${leftDonut}
      <div class="comp-donuts-vs" aria-hidden="true"><span>VS</span></div>
      ${rightDonut}
    </div>
    <div class="comparison-bars-header">
      <h3 class="comparison-visual-heading">Comparative Metric Profiles</h3>
      <p class="comparison-visual-sub">Animated proportional dual-bar comparisons across census indicators</p>
    </div>
    <div class="comparison-bars-grid">
      ${barCards}
    </div>
  </div>`;
}

async function loadFactComparison() {
  const requestId = ++factComparisonRequest;
  const container = document.querySelector('#fact-comparison');
  const leftSlug = state.district?.slug;
  const rightSlug = document.querySelector('#compare-other').value;
  if (!leftSlug || !rightSlug) return;
  if (leftSlug === rightSlug) {
    setBusy(container, false, 'Choose a different second district to compare.');
    return;
  }
  setBusy(container, true, 'Loading comparable census facts…');
  const metrics = ['literacy_total_pct', 'literacy_male_pct', 'literacy_female_pct', 'population_2023', 'out_of_school_children_5_16'];
  try {
    const datasets = await Promise.all(metrics.map(censusData));
    if (requestId !== factComparisonRequest) return;
    const left = state.districts.find(item => item.slug === leftSlug);
    const right = state.districts.find(item => item.slug === rightSlug);
    const cell = (dataset, slug) => {
      const row = dataset.rows.find(item => item.slug === slug);
      if (row?.value == null) return `<td>No figure for ${escapeHtml(dataset.period)}</td>`;
      const anchor = row.citation.anchor_ids?.[0];
      const source = anchor
        ? evidenceButtons([anchor], 'View source')
        : `<a class="source-link" href="${safeUrl(row.citation.url)}" target="_blank" rel="noreferrer">Official table</a>`;
      return `<td>${escapeHtml(number(row.value, dataset.unit === 'percent' ? 2 : 0))}${dataset.unit === 'percent' ? '%' : ''}
        ${source}</td>`;
    };
    container.innerHTML = `<div class="comparison-table-wrap"><table class="comparison-table">
      <caption>Census 2023 · ${escapeHtml(left.name)} and ${escapeHtml(right.name)}</caption>
      <thead><tr><th scope="col">Metric</th><th scope="col">${escapeHtml(left.name)}</th><th scope="col">${escapeHtml(right.name)}</th></tr></thead>
      <tbody>${datasets.map(dataset => `<tr><th scope="row">${escapeHtml(dataset.label)}<small>${escapeHtml(dataset.period)} · ${escapeHtml(dataset.unit)}</small></th>${cell(dataset, leftSlug)}${cell(dataset, rightSlug)}</tr>`).join('')}</tbody></table></div>
      <p class="coverage-note">Punjab Census 2023. A comparable 2017 district literacy series is awaiting review.</p>
      ${renderComparisonCharts(datasets, left, right)}`;
    setBusy(container, false);
  } catch (error) {
    if (requestId !== factComparisonRequest) return;
    container.innerHTML = `<p role="alert">Unable to load comparisons: ${escapeHtml(error.message)}</p><button type="button" data-action="retry-facts">Retry comparison</button>`;
    setBusy(container, false);
  }
}

async function loadCensusRankings(requestId) {
  const container = document.querySelector('#ranking-list');
  setBusy(container, true, 'Loading census positions…');
  let dataset;
  try {
    dataset = await censusData(rankingCategory.value.slice('census:'.length));
  } catch (error) {
    if (requestId !== state.rankingRequest) return;
    throw error;
  }
  if (requestId !== state.rankingRequest) return;
  document.querySelector('#ranking-note').textContent = `${dataset.label} · Census ${dataset.period} · ${dataset.rows.length} districts. ${dataset.note}`;
  if (!dataset.rows.length) { setBusy(container, false, 'No comparable facts available.'); return; }
  const maximum = dataset.unit === 'percent' ? 100 : Math.max(...dataset.rows.map(item => item.value), 1);
  container.innerHTML = `<li class="chart-scale" aria-hidden="true"><span>0</span><span>${escapeHtml(number(maximum))}${dataset.unit === 'percent' ? '%' : ''}</span></li>` + dataset.rows.map(item => {
    const value = `${number(item.value, dataset.unit === 'percent' ? 2 : 0)}${dataset.unit === 'percent' ? '%' : ''}`;
    const width = Math.max(0, Math.min(100, item.value / maximum * 100));
    return `<li class="census-bar ${state.district?.slug === item.slug ? 'active' : ''}">
      <span class="position" aria-label="Position ${item.position}">${item.position}</span>
      <span><a href="#/district/${encodeURIComponent(item.slug)}">${escapeHtml(item.name)}</a><span class="bar-track"><span class="bar" style="display:block;width:${width}%"></span></span></span>
      <span class="bar-value"><strong>${escapeHtml(value)}</strong><a class="source-link" href="${safeUrl(item.citation.url)}" title="${escapeHtml(item.citation.locator)}" target="_blank" rel="noreferrer">Source</a></span></li>`;
  }).join('');
  setBusy(container, false);
}

function renderYearChart(data) {
  const container = document.querySelector('#year-chart');
  document.querySelector('#trend-district-label').textContent = data.district_name;
  const periods = data.periods;
  if (periods.length < 2) { container.textContent = 'At least two comparable periods are required.'; return; }
  const x = index => 80 + index * 470 / (periods.length - 1);
  const y = value => 180 - value * 1.5;
  const points = periods.map((period, index) => `${x(index)},${y(period.utilization_pct)}`).join(' ');
  container.innerHTML = `<svg viewBox="0 0 640 240" role="img" aria-labelledby="year-chart-title year-chart-description">
    <title id="year-chart-title">${escapeHtml(data.district_name)} yearly development-budget utilization</title>
    <desc id="year-chart-description">${periods.map(period => `${escapeHtml(period.period)}: ${escapeHtml(number(period.utilization_pct, 2))} percent`).join('; ')}. Exact data follows the graph.</desc>
    ${[0, 25, 50, 75, 100].map(value => `<line x1="65" x2="570" y1="${y(value)}" y2="${y(value)}" class="chart-grid"/><text x="52" y="${y(value) + 4}" text-anchor="end">${value}%</text>`).join('')}
    <polyline points="${points}" fill="none" class="chart-line"/>
    ${periods.map((period, index) => `<circle cx="${x(index)}" cy="${y(period.utilization_pct)}" r="5" class="chart-point"/><text x="${x(index)}" y="${y(period.utilization_pct) - 12}" text-anchor="middle">${escapeHtml(number(period.utilization_pct, 2))}%</text><text x="${x(index)}" y="210" text-anchor="middle">${escapeHtml(period.period)}</text>`).join('')}
    </svg><p class="coverage-note">Only published comparable periods are plotted. The line connects the two observations; it is not a forecast.</p>
    <div class="comparison-table-wrap"><table class="comparison-table"><caption>Exact yearly values</caption><thead><tr><th scope="col">Period</th><th scope="col">Utilization</th></tr></thead><tbody>${periods.map(period => `<tr><th scope="row">${escapeHtml(period.period)}</th><td>${escapeHtml(number(period.utilization_pct, 2))}%</td></tr>`).join('')}</tbody></table></div>`;
}
