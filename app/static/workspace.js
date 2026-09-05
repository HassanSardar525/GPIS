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
  const parts = location.hash.split('/');
  const page = ['overview', 'district', 'compare'].includes(parts[1]) ? parts[1] : 'overview';
  document.querySelectorAll('[data-page]').forEach(element => { element.hidden = element.dataset.page !== page; });
  document.querySelectorAll('[data-nav]').forEach(link => {
    if (link.dataset.nav === page) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  document.title = `${page === 'district' ? 'District Profile & Ask GPIS' : page === 'compare' ? 'Compare & Trends' : 'Overview'} · GPIS`;
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

function initWorkspaceNavigation() {
  const other = document.querySelector('#compare-other');
  other.innerHTML = state.districts.map(item => `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)}</option>`).join('');
  other.value = state.districts.find(item => item.slug !== select.value)?.slug || select.value;
  if (!workspaceReady) {
    window.addEventListener('hashchange', () => navigateWorkspace());
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
  if (location.hash.startsWith('#/district')) history.replaceState(null, '', profile);
  if (location.hash.startsWith('#/compare')) loadFactComparison();
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
  const metrics = ['population_2023', 'literacy_total_pct', 'literacy_male_pct', 'literacy_female_pct', 'out_of_school_children_5_16'];
  try {
    const datasets = await Promise.all(metrics.map(censusData));
    if (requestId !== factComparisonRequest) return;
    const left = state.districts.find(item => item.slug === leftSlug);
    const right = state.districts.find(item => item.slug === rightSlug);
    const cell = (dataset, slug) => {
      const row = dataset.rows.find(item => item.slug === slug);
      if (!row) return '<td>Unavailable</td>';
      return `<td>${escapeHtml(number(row.value, dataset.unit === 'percent' ? 2 : 0))}${dataset.unit === 'percent' ? '%' : ''}
        <a class="source-link" href="${safeUrl(row.citation.url)}" target="_blank" rel="noreferrer" title="${escapeHtml(row.citation.locator)}">Source</a></td>`;
    };
    container.innerHTML = `<div class="comparison-table-wrap"><table class="comparison-table">
      <caption>Census 2023 · ${escapeHtml(left.name)} and ${escapeHtml(right.name)}</caption>
      <thead><tr><th scope="col">Metric</th><th scope="col">${escapeHtml(left.name)}</th><th scope="col">${escapeHtml(right.name)}</th></tr></thead>
      <tbody>${datasets.map(dataset => `<tr><th scope="row">${escapeHtml(dataset.label)}</th>${cell(dataset, leftSlug)}${cell(dataset, rightSlug)}</tr>`).join('')}</tbody></table></div>
      <p class="coverage-note">One census snapshot. These facts do not establish a yearly trend or an overall performance score.</p>`;
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
