function createSessionId() {
  return window.crypto?.randomUUID?.() || `session-${Date.now()}`;
}

function savedSessionId() {
  try { return window.localStorage.getItem('gpis.sessionId'); } catch { return null; }
}

function saveSessionId(sessionId) {
  try { window.localStorage.setItem('gpis.sessionId', sessionId); } catch { /* storage is optional */ }
}

function savedModel() {
  try { return window.localStorage.getItem('gpis.selectedModel'); } catch { return null; }
}

function saveModel(model) {
  try { window.localStorage.setItem('gpis.selectedModel', model); } catch { /* optional */ }
}

const restoredSessionId = savedSessionId();
const state = {
  district: null,
  districts: [],
  trend: null,
  sessionId: restoredSessionId || createSessionId(),
  sessionStarted: Boolean(restoredSessionId),
  selectedModel: savedModel() || '',
  models: [],
  districtRequest: 0,
  rankingRequest: 0,
  chatRequest: 0,
  lastQuestion: null,
  lastDistricts: [],
};
const select = document.querySelector('#district-select');
const rankingCategory = document.querySelector('#ranking-category');
const initialChatMessage = 'Try: “Why did this district receive its health score?” or “How did budget utilization change?”';

const number = (value, digits = 0) => value == null ? 'Unavailable' : Number(value).toLocaleString('en-PK', {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
});

const escapeHtml = value => String(value).replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
})[character]);

function safeUrl(value) {
  try {
    const parsed = new URL(value, window.location.origin);
    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '#';
  } catch {
    return '#';
  }
}

function setBusy(element, busy, message = null) {
  element.setAttribute('aria-busy', String(busy));
  element.dataset.state = busy ? 'loading' : 'ready';
  if (message !== null) element.textContent = message;
}

function renderCitations(citations = []) {
  if (!citations.length) return '';
  const cards = citations.map((citation, index) => {
    const sourceUrl = safeUrl(citation.url);
    const officialLink = sourceUrl === '#'
      ? '<span class="citation-empty">Official source link unavailable.</span>'
      : `<a href="${sourceUrl}" target="_blank" rel="noreferrer">Open official source ↗</a>`;
    const passage = citation.passage
      ? `<blockquote>${escapeHtml(citation.passage)}</blockquote>`
      : '<p class="citation-empty">No retrieved passage is available for this citation.</p>';
    return `<details class="citation-preview">
      <summary><span>Source ${index + 1}</span><strong>${escapeHtml(citation.title)}</strong><small>${escapeHtml(citation.publisher)} · ${escapeHtml(citation.period)}</small></summary>
      <div class="citation-body">
        <dl><div><dt>Publisher</dt><dd>${escapeHtml(citation.publisher)}</dd></div><div><dt>Period</dt><dd>${escapeHtml(citation.period)}</dd></div><div><dt>Page / table</dt><dd>${escapeHtml(citation.locator)}</dd></div></dl>
        <h4>Retrieved passage</h4>
        ${passage}
        ${officialLink}
      </div>
    </details>`;
  }).join('');
  return `<section class="citation-list" aria-label="Evidence sources"><h3>Evidence sources</h3>${cards}</section>`;
}

function renderAnswerStatus(data) {
  if (data.mode === 'abstained') {
    return '<p class="answer-status state-empty">No matching evidence was found. Try a district literacy, health-facility, budget, score, ranking, or source question.</p>';
  }
  const fallback = data.mode === 'extractive' && data.warnings?.some(warning => warning.includes('LLM'));
  return fallback
    ? '<p class="answer-status state-fallback">A deterministic fallback answer is shown because the language-model response was unavailable or failed citation checks.</p>'
    : '';
}

function setChatControlsDisabled(disabled) {
  document.querySelector('#chat-submit').disabled = disabled;
  document.querySelectorAll('.chat-prompts button').forEach(button => { button.disabled = disabled; });
  document.querySelectorAll('[data-score-category]').forEach(button => { button.disabled = disabled; });
  document.querySelector('#delete-chat').disabled = disabled || !state.sessionStarted;
  const modelSelect = document.querySelector('#model-select');
  if (modelSelect) modelSelect.disabled = disabled;
}

async function loadModels() {
  const modelSelect = document.querySelector('#model-select');
  if (!modelSelect) return;
  try {
    const data = await json('/api/v1/models');
    state.models = data.models || [];
    if (!state.models.length) return;

    const validModel = state.models.some(m => m.id === state.selectedModel);
    if (!validModel) {
      state.selectedModel = data.default_model || state.models[0].id;
      saveModel(state.selectedModel);
    }

    modelSelect.innerHTML = state.models.map(m => {
      const selected = m.id === state.selectedModel ? 'selected' : '';
      return `<option value="${escapeHtml(m.id)}" ${selected}>${escapeHtml(m.name)}</option>`;
    }).join('');
  } catch (error) {
    modelSelect.innerHTML = '<option value="fallback" selected>Deterministic Fallback (Extractive)</option>';
    state.selectedModel = 'fallback';
  }
}

function showDistrictError(error) {
  document.querySelector('#district-summary').setAttribute('aria-busy', 'false');
  document.querySelector('#district-name').textContent = 'District unavailable';
  document.querySelector('#scorecards').innerHTML = `<div class="state-error" role="alert"><p>${escapeHtml(error.message)}</p><button type="button" data-action="retry-district">Retry district</button></div>`;
  renderTrendError(error);
}

function showRankingError(error) {
  const list = document.querySelector('#ranking-list');
  list.innerHTML = `<li class="state-error" role="alert"><span>${escapeHtml(error.message)}</span><button type="button" data-action="retry-ranking">Retry</button></li>`;
  setBusy(list, false);
}

function startNewChat(message = initialChatMessage) {
  state.chatRequest += 1;
  state.sessionId = createSessionId();
  state.sessionStarted = false;
  saveSessionId(state.sessionId);
  state.lastQuestion = null;
  state.lastDistricts = [];
  setChatControlsDisabled(false);
  const answer = document.querySelector('#chat-answer');
  setBusy(answer, false, message);
  document.querySelector('#chat-question').value = '';
  document.querySelector('#chat-question').focus();
}

async function deleteCurrentChat() {
  if (!state.sessionStarted) return;
  if (!window.confirm('Delete this conversation and its stored history?')) return;
  const button = document.querySelector('#delete-chat');
  button.disabled = true;
  try {
    await json(`/api/v1/sessions/${encodeURIComponent(state.sessionId)}`, { method: 'DELETE' });
    startNewChat('Conversation deleted. A new empty chat is ready.');
  } catch (error) {
    document.querySelector('#chat-answer').innerHTML = `<div class="state-error" role="alert"><p>Could not delete this conversation: ${escapeHtml(error.message)}</p><button type="button" data-action="retry-delete">Retry deletion</button></div>`;
    button.disabled = false;
  }
}

function comparisonValue(value, unit) {
  const digits = Number.isInteger(Number(value)) ? 0 : 2;
  const suffix = unit === '%' ? '%' : unit === 'count' ? '' : ` ${unit}`;
  return `${number(value, digits)}${suffix}`;
}

function signedComparisonValue(value, unit) {
  const prefix = Number(value) > 0 ? '+' : '';
  return `${prefix}${comparisonValue(value, unit)}`;
}

function renderScoreQuality(detail) {
  if (!detail) return '';
  const confidence = detail.confidence == null ? 'unassessed' : number(detail.confidence, 2);
  const warnings = detail.warnings?.length
    ? `<ul>${detail.warnings.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
    : '';
  return `<div class="score-quality">
    <span>${escapeHtml(detail.version)}</span>
    <span>${escapeHtml(detail.reporting_period)}</span>
    <span>Coverage ${escapeHtml(number(detail.coverage * 100, 0))}% · confidence ${escapeHtml(confidence)}</span>
    ${warnings}
  </div>`;
}

function renderComparison(comparison) {
  if (!comparison || comparison.districts?.length !== 2) return '';
  const [left, right] = comparison.districts;
  const components = comparison.components.map(component => `<tr>
    <th scope="row">${escapeHtml(component.label)}<small>${escapeHtml(component.unit)}</small></th>
    <td>${escapeHtml(comparisonValue(component.values[left.slug], component.unit))}</td>
    <td>${escapeHtml(comparisonValue(component.values[right.slug], component.unit))}</td>
    <td class="comparison-delta">${escapeHtml(signedComparisonValue(component.delta, component.unit))}</td>
  </tr>`).join('');
  const trends = comparison.trends?.length ? `<div class="comparison-trends">
    <h4>Development-budget utilization trend</h4>
    ${comparison.trends.map(trend => {
      const [previous, current] = trend.periods;
      return `<article>
        <strong>${escapeHtml(trend.district_name)}</strong>
        <span>${escapeHtml(previous.period)}: ${escapeHtml(comparisonValue(previous.utilization_pct, '%'))}</span>
        <span>${escapeHtml(current.period)}: ${escapeHtml(comparisonValue(current.utilization_pct, '%'))}</span>
        <b>${escapeHtml(signedComparisonValue(trend.change_percentage_points, 'pp'))}</b>
      </article>`;
    }).join('')}
  </div>` : '';
  const limitations = comparison.limitations?.length
    ? `<ul class="comparison-limitations">${comparison.limitations.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
    : '';
  return `<section class="comparison-result" aria-label="${escapeHtml(comparison.category)} district comparison">
    <div class="comparison-heading">
      <h3>${escapeHtml(comparison.category)} comparison</h3>
      <span>Right − left score: ${escapeHtml(signedComparisonValue(comparison.score_delta, 'points'))}</span>
    </div>
    <div class="comparison-districts">
      ${[left, right].map(district => `<article>
        <span>${escapeHtml(district.name)}</span>
        <strong>${escapeHtml(number(district.score, 1))}</strong>
        <small>Rank ${escapeHtml(district.rank)}</small>
        ${renderScoreQuality(district.score_detail)}
      </article>`).join('')}
    </div>
    <div class="comparison-table-wrap"><table class="comparison-table">
      <caption>Component values and ${escapeHtml(right.name)} minus ${escapeHtml(left.name)} differences</caption>
      <thead><tr><th>Component</th><th>${escapeHtml(left.name)}</th><th>${escapeHtml(right.name)}</th><th>Difference</th></tr></thead>
      <tbody>${components}</tbody>
    </table></div>
    ${trends}${limitations}
  </section>`;
}

async function json(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message || data.error || 'Request failed');
    error.code = data.error?.code;
    throw error;
  }
  return data;
}

function card(category, title, score, rank, detail, metrics, sourceUrl) {
  return `<article class="score-card">
    <div class="score-top"><div><h3>${escapeHtml(title)}</h3><span class="rank">Rank ${rank.rank} of ${state.districts.filter(item => item.scores[category] != null).length}</span></div><button class="score-number" type="button" data-score-category="${category}" title="Ask why this score was given">${score}</button></div>
    ${renderScoreQuality(detail)}
    <ul class="metric-list">${metrics.map(([label, value]) => `<li><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></li>`).join('')}</ul>
    <a class="source-link" href="${safeUrl(sourceUrl)}" target="_blank" rel="noreferrer">View official source ↗</a>
  </article>`;
}

function officialServiceCards(data) {
  const labels = {hospitals: 'Hospitals', dispensaries: 'Dispensaries', rhcs: 'RHCs', bhus: 'BHUs', tb_clinics: 'TB clinics', sh_centers: 'Sub-health centres', mch_centers: 'Maternal and child health centres', trauma_centers: 'Trauma centres'};
  const health = data.official_health;
  const budget = data.official_budget;
  let html = '';
  if (health) {
    const values = Object.fromEntries(health.observations.map(row => [row.metric_key, row.value]));
    const display = value => value == null ? '—' : number(value);
    const source = Object.values(health.sources)[0];
    html += `<article class="score-card"><h3>Official health capacity</h3><p>As at ${escapeHtml(health.period)} · Punjab Health Statistics</p>
      <table><thead><tr><th>Facility</th><th>Institutions</th><th>Beds</th></tr></thead><tbody>${Object.entries(labels).map(([key, label]) => `<tr><th>${escapeHtml(label)}</th><td>${display(values[`phs_${key}_count`])}</td><td>${display(values[`phs_${key}_beds`])}</td></tr>`).join('')}</tbody></table>
      <p class="muted">— = printed dash (nil or insignificant), not a confirmed zero. Capacity does not measure quality of care.</p><a class="source-link" href="${safeUrl(source.url)}" target="_blank" rel="noreferrer">View official health source ↗</a></article>`;
  }
  if (budget) {
    const values = Object.fromEntries(budget.observations.map(row => [row.metric_key, row.value]));
    const source = Object.values(budget.sources)[0];
    html += `<article class="score-card"><h3>Health-authority budget</h3><p>${escapeHtml(budget.period)} · Rs million</p>
      <ul class="metric-list">${[['Total budget', 'total_budget'], ['Total expenditure', 'total_expenditure'], ['Development budget', 'development_budget'], ['Development expenditure', 'development_expenditure']].map(([label,key]) => `<li><span>${label}</span><strong>${number(values[`dha_${key}_million_pkr`],3)}</strong></li>`).join('')}</ul>
      <p class="muted">District Health Authority spending only. North Punjab figures are FY 2022–23; South Punjab figures are FY 2023–24. These are not a same-year ranking.</p><a class="source-link" href="${safeUrl(source.url)}" target="_blank" rel="noreferrer">View official budget source ↗</a></article>`;
  }
  return html;
}

function renderDistrict(data) {
  state.district = data;
  if (typeof syncWorkspaceDistrict === 'function') syncWorkspaceDistrict(data);
  setBusy(document.querySelector('#notice'), false, data.metadata.disclaimer);
  document.querySelector('#district-name').textContent = data.name;
  document.querySelector('#population').textContent = `Population ${number(data.population_2023)} · Census 2023`;
  document.querySelector('#overall-score').dataset.available = String(data.derived.scores.overall != null);
  if (data.derived.scores.overall == null) {
    document.querySelector('#overall-score').textContent = 'Unavailable';
    document.querySelector('#overall-rank').textContent = 'Not ranked';
    document.querySelector('#overall-quality').textContent = 'Official facts available; outside the ten-district score cohort.';
    const education = data.education;
    document.querySelector('#scorecards').innerHTML = `<article class="score-card">
      <h3>Census 2023 education</h3>
      <ul class="metric-list">
        <li><span>Total literacy</span><strong>${escapeHtml(number(education.literacy_total_pct, 2))}%</strong></li>
        <li><span>Male literacy</span><strong>${escapeHtml(number(education.literacy_male_pct, 2))}%</strong></li>
        <li><span>Female literacy</span><strong>${escapeHtml(number(education.literacy_female_pct, 2))}%</strong></li>
        <li><span>Out-of-school age 5–16</span><strong>${escapeHtml(number(education.out_of_school_children_5_16))}</strong></li>
      </ul><a class="source-link" href="${safeUrl(data.sources.pbs_table_12?.url)}" target="_blank" rel="noreferrer">View official source ↗</a>
      </article>` + officialServiceCards(data);
    setBusy(document.querySelector('#notice'), false, (data.data_warnings || []).join(' '));
    loadRankings().catch(showRankingError);
    return;
  }
  document.querySelector('#overall-score').textContent = data.derived.scores.overall;
  document.querySelector('#overall-rank').textContent = `Rank ${data.rankings.overall.rank} of ${state.districts.filter(item => item.scores.overall != null).length}`;
  document.querySelector('#overall-quality').innerHTML = renderScoreQuality(data.score_details.overall);

  const education = data.education;
  const health = data.health;
  const accountability = data.accountability;
  document.querySelector('#scorecards').innerHTML = [
    card('education', 'Education', data.derived.scores.education, data.rankings.education, data.score_details.education, [
      ['Total literacy', `${number(education.literacy_total_pct, 1)}%`],
      ['Female literacy', `${number(education.literacy_female_pct, 1)}%`],
      ['Out-of-school age 5–16', number(education.out_of_school_children_5_16)],
    ], data.sources.pbs_table_12.url),
    card('health', 'Health access proxy', data.derived.scores.health, data.rankings.health, data.score_details.health, [
      ['Listed public facilities', number(data.derived.facility_count)],
      ['Facilities per 100k', number(data.derived.facilities_per_100k, 2)],
      ['BHUs / RHCs', `${number(health.bhus)} / ${number(health.rhcs)}`],
    ], data.sources.agp_dha.url),
    card('accountability', 'Financial management proxy', data.derived.scores.accountability, data.rankings.accountability, data.score_details.accountability, [
      ['Overall budget utilized', `${number(100 - accountability.overall_budget_lapse_pct, 1)}%`],
      ['Development budget utilized', `${number(100 - accountability.development_budget_lapse_pct, 1)}%`],
      ['Formations audited', `${accountability.audited_formations} of ${accountability.total_formations}`],
    ], data.sources.agp_dha.url),
  ].join('') + officialServiceCards(data);
  loadRankings().catch(showRankingError);
}

function renderTrend(data) {
  state.trend = data;
  if (typeof renderYearChart === 'function') renderYearChart(data);
  const signedChange = `${data.change_percentage_points > 0 ? '+' : ''}${number(data.change_percentage_points, 2)} pp`;
  const change = document.querySelector('#trend-change');
  change.textContent = `${signedChange} · ${data.direction}`;
  change.dataset.direction = data.direction;
  document.querySelector('#trend-periods').innerHTML = data.periods.map(period => `<article>
    <span>${escapeHtml(period.period)}</span>
    <strong>${number(period.utilization_pct, 2)}%</strong>
    <small>Rs ${number(period.expenditure_million_pkr, 3)}m spent of Rs ${number(period.final_grant_million_pkr, 3)}m final grant</small>
  </article>`).join('');
  document.querySelector('#trend-warning').textContent = data.warnings.join(' ');
  document.querySelector('#trend-source').href = safeUrl(data.citation.url);
  document.querySelector('#trend-panel').setAttribute('aria-busy', 'false');
}

function renderTrendError(error) {
  state.trend = null;
  document.querySelector('#year-chart')?.replaceChildren();
  const trendLabel = document.querySelector('#trend-district-label');
  if (trendLabel) trendLabel.textContent = state.district?.name || '';
  document.querySelector('#trend-change').textContent = 'Unavailable';
  document.querySelector('#trend-periods').innerHTML = '';
  document.querySelector('#trend-warning').textContent = error.message;
  document.querySelector('#trend-source').removeAttribute('href');
  document.querySelector('#trend-panel').setAttribute('aria-busy', 'false');
}

async function loadDistrict(slug) {
  const requestId = ++state.districtRequest;
  setBusy(document.querySelector('#district-summary'), true);
  document.querySelector('#district-name').textContent = 'Loading…';
  document.querySelector('#scorecards').innerHTML = '<article class="score-card skeleton" aria-hidden="true"></article><article class="score-card skeleton" aria-hidden="true"></article><article class="score-card skeleton" aria-hidden="true"></article>';
  document.querySelector('#trend-panel').setAttribute('aria-busy', 'true');
  document.querySelector('#trend-change').textContent = 'Loading…';
  let detail;
  let trend;
  try {
    [detail, trend] = await Promise.all([
      json(`/api/v1/districts/${slug}`),
      json(`/api/v1/districts/${slug}/trends/development-budget`).catch(error => ({ error })),
    ]);
  } catch (error) {
    if (requestId !== state.districtRequest) return;
    throw error;
  }
  if (requestId !== state.districtRequest) return;
  renderDistrict(detail);
  if (trend.error) renderTrendError(trend.error); else renderTrend(trend);
  setBusy(document.querySelector('#district-summary'), false);
}

async function loadRankings() {
  const requestId = ++state.rankingRequest;
  if (rankingCategory.value.startsWith('census:')) {
    return loadCensusRankings(requestId);
  }
  const note = document.querySelector('#ranking-note');
  if (note) note.textContent = 'Reviewed performance scores: fixed ten-district cohort. Districts without a score are not ranked.';
  setBusy(document.querySelector('#ranking-list'), true, 'Loading rankings…');
  let data;
  try {
    data = await json(`/api/v1/rankings?category=${rankingCategory.value}`);
  } catch (error) {
    if (requestId !== state.rankingRequest) return;
    throw error;
  }
  if (requestId !== state.rankingRequest) return;
  if (!data.rankings.length) {
    setBusy(document.querySelector('#ranking-list'), false, 'No rankable districts are available for this category.');
    return;
  }
  document.querySelector('#ranking-list').innerHTML = data.rankings.map(item => `
    <li class="${state.district?.slug === item.slug ? 'active' : ''}">
      <strong>${item.rank}</strong>
      <span>${escapeHtml(item.name)}<span class="bar-track"><span class="bar" style="display:block;width:${item.score}%"></span></span></span>
      <strong title="${escapeHtml(`${item.score_detail.version}; ${item.score_detail.reporting_period}; coverage ${number(item.score_detail.coverage * 100, 0)}%`)}">${item.score}</strong>
    </li>`).join('');
  setBusy(document.querySelector('#ranking-list'), false);
}

async function askQuestion(question, districts = [state.district.slug]) {
  if (location.hash.startsWith('#/compare') || location.hash === '#/overview') location.hash = '#/district/' + state.district.slug;
  const answer = document.querySelector('#chat-answer');
  const requestId = ++state.chatRequest;
  state.lastQuestion = question;
  state.lastDistricts = [...districts];
  setChatControlsDisabled(true);
  setBusy(answer, true, 'Searching structured facts and official evidence…');
  try {
    const data = await json('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        districts,
        session_id: state.sessionId,
        model: state.selectedModel || undefined,
      }),
    });
    if (requestId !== state.chatRequest) return;
    state.sessionId = data.session_id || state.sessionId;
    state.sessionStarted = true;
    saveSessionId(state.sessionId);
    const warnings = data.warnings.map(warning => `<li>${escapeHtml(warning)}</li>`).join('');
    const tools = data.tools_used?.length ? `<span>tools: ${escapeHtml(data.tools_used.join(', '))}</span>` : '';
    const comparison = renderComparison(data.comparison);
    const mode = ['groq', 'gemini', 'extractive', 'abstained'].includes(data.mode) ? data.mode : 'extractive';
    const modelBadge = data.model || data.mode;
    answer.innerHTML = `<div class="answer-meta"><span class="answer-mode mode-${mode}">${escapeHtml(modelBadge)}</span><span>${escapeHtml(data.route)}</span>${tools}<span>trace ${escapeHtml(String(data.trace_id).slice(0, 8))}</span></div>${renderAnswerStatus(data)}<p>${escapeHtml(data.answer)}</p>${comparison}${renderCitations(data.citations)}${warnings ? `<ul class="chat-warnings">${warnings}</ul>` : ''}`;
    setBusy(answer, false);
    answer.focus({ preventScroll: true });
  } catch (error) {
    if (requestId !== state.chatRequest) return;
    answer.innerHTML = error.code === 'session_expired'
      ? '<div class="state-error" role="alert"><p>This conversation expired and cannot be resumed.</p><button type="button" data-action="new-chat">Start a new chat</button></div>'
      : `<div class="state-error" role="alert"><p>Evidence service unavailable: ${escapeHtml(error.message)}</p><button type="button" data-action="retry-chat">Retry question</button></div>`;
    setBusy(answer, false);
  } finally {
    if (requestId === state.chatRequest) setChatControlsDisabled(false);
  }
}

function filterDistricts() {
  const results = document.querySelector('#district-results');
  const query = document.querySelector('#district-query').value.trim();
  const normalize = value => value.toLowerCase().replace(/[^a-z0-9]/g, '');
  const needle = normalize(query);
  const matches = state.districts.filter(district => {
    const aliases = district.slug === 'dera-ghazi-khan' ? ' DG Khan D.G. Khan' : '';
    return normalize(district.name + aliases).includes(needle);
  });
  results.innerHTML = matches.length
    ? matches.map(district => `<option value="${escapeHtml(district.slug)}">${escapeHtml(district.name)}</option>`).join('')
    : '<option value="">No matching districts</option>';
  results.disabled = matches.length === 0;
  results.size = query ? Math.max(2, Math.min(matches.length, 5)) : 1;
  if (query && matches.length) results.selectedIndex = -1;
  results.hidden = !query;
  document.querySelector('#district-search-status').textContent = query
    ? (matches.length ? `${matches.length} matching district${matches.length === 1 ? '' : 's'}. Choose a result or press Enter.` : 'No matching districts. Try another name.')
    : 'District-level official data';
}

async function init() {
  select.disabled = true;
  select.innerHTML = '<option value="">Loading districts...</option>';
  setBusy(document.querySelector('#notice'), true, 'Loading reviewed district evidence…');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let data;
  try {
    data = await json('/api/v1/districts', { signal: controller.signal });
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('District data took too long to load. Check the database connection and retry.');
    throw error;
  } finally {
    clearTimeout(timeout);
  }
  if (!data.districts.length) {
    setBusy(document.querySelector('#notice'), false, 'No reviewed districts are currently available.');
    select.disabled = true;
    setBusy(document.querySelector('#district-summary'), false);
    document.querySelector('#district-name').textContent = 'No districts available';
    document.querySelector('#scorecards').innerHTML = '<div class="state-empty">No scorecards can be displayed.</div>';
    renderTrendError(new Error('No trend evidence is available.'));
    setBusy(document.querySelector('#ranking-list'), false, 'No rankable districts are available.');
    return;
  }
  state.districts = data.districts;
  select.innerHTML = data.districts.map(district => `<option value="${escapeHtml(district.slug)}">${escapeHtml(district.name)}</option>`).join('');
  select.disabled = false;
  filterDistricts();
  const requestedSlug = location.hash.split('/')[2];
  const initialSlug = data.districts.some(item => item.slug === requestedSlug) ? requestedSlug : data.districts[0].slug;
  select.value = initialSlug;
  initWorkspaceNavigation();
  await Promise.all([loadDistrict(initialSlug), loadModels()]);
}

select.addEventListener('change', () => {
  if (select.value) loadDistrict(select.value).catch(showDistrictError);
});
document.querySelector('#district-results').addEventListener('change', event => {
  const slug = event.target.value;
  if (slug) {
    select.value = slug;
    loadDistrict(slug).catch(showDistrictError);
  }
});
document.querySelector('#district-query').addEventListener('input', filterDistricts);
document.querySelector('#district-query').addEventListener('keydown', event => {
  const results = document.querySelector('#district-results');
  if (event.key === 'Enter' && !results.hidden && !results.disabled) {
    event.preventDefault();
    const slug = results.value || results.options[0]?.value;
    if (slug) {
      select.value = slug;
      loadDistrict(slug).catch(showDistrictError);
    }
  } else if (event.key === 'ArrowDown' && !results.hidden && !results.disabled) {
    event.preventDefault();
    results.focus();
  } else if (event.key === 'Escape') {
    event.target.value = '';
    filterDistricts();
  }
});
rankingCategory.addEventListener('change', () => loadRankings().catch(showRankingError));

document.querySelector('#model-select')?.addEventListener('change', event => {
  state.selectedModel = event.target.value;
  saveModel(state.selectedModel);
});

document.querySelector('#scorecards').addEventListener('click', event => {
  const button = event.target.closest('[data-score-category]');
  if (!button) return;
  const category = button.dataset.scoreCategory;
  const question = `Why did ${state.district.name} receive its ${category} score?`;
  document.querySelector('#chat-question').value = '';
  askQuestion(question);
});

document.querySelector('#chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = document.querySelector('#chat-question');
  const question = input.value.trim();
  if (question) {
    input.value = '';
    await askQuestion(question);
  }
});

document.querySelector('#new-chat').addEventListener('click', () => startNewChat());
document.querySelector('#delete-chat').addEventListener('click', deleteCurrentChat);

document.addEventListener('click', event => {
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (action === 'retry-chat' && state.lastQuestion) {
    askQuestion(state.lastQuestion, state.lastDistricts);
  } else if (action === 'retry-district') {
    loadDistrict(select.value).catch(showDistrictError);
  } else if (action === 'retry-ranking') {
    loadRankings().catch(showRankingError);
  } else if (action === 'retry-init') {
    init().catch(showInitError);
  } else if (action === 'retry-delete') {
    deleteCurrentChat();
  } else if (action === 'new-chat') {
    startNewChat();
  }
});

document.querySelectorAll('.chat-prompts button').forEach(button => {
  button.addEventListener('click', () => {
    const question = button.dataset.question.replace('this district', state.district.name);
    document.querySelector('#chat-question').value = '';
    askQuestion(question, button.dataset.allDistricts === 'true' ? [] : [state.district.slug]);
  });
});

function showInitError(error) {
  if (!state.districts.length) {
    select.disabled = true;
    select.innerHTML = '<option value="">District list unavailable - retry below</option>';
    document.querySelector('#district-name').textContent = 'District data unavailable';
    setBusy(document.querySelector('#district-summary'), false);
  }
  const notice = document.querySelector('#notice');
  notice.innerHTML = `<div class="state-error" role="alert"><span>Unable to load district evidence: ${escapeHtml(error.message)}</span><button type="button" data-action="retry-init">Retry</button></div>`;
  setBusy(notice, false);
}

setChatControlsDisabled(false);
init().catch(showInitError);
