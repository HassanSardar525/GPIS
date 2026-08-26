const state = {
  district: null,
  districts: [],
  trend: null,
  sessionId: window.crypto?.randomUUID?.() || `session-${Date.now()}`,
};
const select = document.querySelector('#district-select');
const rankingCategory = document.querySelector('#ranking-category');

const number = (value, digits = 0) => Number(value).toLocaleString('en-PK', {
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

function comparisonValue(value, unit) {
  const digits = Number.isInteger(Number(value)) ? 0 : 2;
  const suffix = unit === '%' ? '%' : unit === 'count' ? '' : ` ${unit}`;
  return `${number(value, digits)}${suffix}`;
}

function signedComparisonValue(value, unit) {
  const prefix = Number(value) > 0 ? '+' : '';
  return `${prefix}${comparisonValue(value, unit)}`;
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
  if (!response.ok) throw new Error(data.error?.message || data.error || 'Request failed');
  return data;
}

function card(category, title, score, rank, metrics, sourceUrl) {
  return `<article class="score-card">
    <div class="score-top"><div><h3>${escapeHtml(title)}</h3><span class="rank">Rank ${rank.rank} of ${state.districts.length}</span></div><button class="score-number" type="button" data-score-category="${category}" title="Ask why this score was given">${score}</button></div>
    <ul class="metric-list">${metrics.map(([label, value]) => `<li><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></li>`).join('')}</ul>
    <a class="source-link" href="${safeUrl(sourceUrl)}" target="_blank" rel="noreferrer">View official source ↗</a>
  </article>`;
}

function renderDistrict(data) {
  state.district = data;
  document.querySelector('#notice').textContent = data.metadata.disclaimer;
  document.querySelector('#district-name').textContent = data.name;
  document.querySelector('#population').textContent = `Population ${number(data.population_2023)} · Census 2023`;
  document.querySelector('#overall-score').textContent = data.derived.scores.overall;
  document.querySelector('#overall-rank').textContent = `Rank ${data.rankings.overall.rank} of ${state.districts.length}`;

  const education = data.education;
  const health = data.health;
  const accountability = data.accountability;
  document.querySelector('#scorecards').innerHTML = [
    card('education', 'Education', data.derived.scores.education, data.rankings.education, [
      ['Total literacy', `${number(education.literacy_total_pct, 1)}%`],
      ['Female literacy', `${number(education.literacy_female_pct, 1)}%`],
      ['Out-of-school age 5–16', number(education.out_of_school_children_5_16)],
    ], data.sources.pbs_table_12.url),
    card('health', 'Health access proxy', data.derived.scores.health, data.rankings.health, [
      ['Listed public facilities', number(data.derived.facility_count)],
      ['Facilities per 100k', number(data.derived.facilities_per_100k, 2)],
      ['BHUs / RHCs', `${number(health.bhus)} / ${number(health.rhcs)}`],
    ], data.sources.agp_dha.url),
    card('accountability', 'Financial management proxy', data.derived.scores.accountability, data.rankings.accountability, [
      ['Overall budget utilized', `${number(100 - accountability.overall_budget_lapse_pct, 1)}%`],
      ['Development budget utilized', `${number(100 - accountability.development_budget_lapse_pct, 1)}%`],
      ['Formations audited', `${accountability.audited_formations} of ${accountability.total_formations}`],
    ], data.sources.agp_dha.url),
  ].join('');
  loadRankings();
}

function renderTrend(data) {
  state.trend = data;
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
}

function renderTrendError(error) {
  document.querySelector('#trend-change').textContent = 'Unavailable';
  document.querySelector('#trend-periods').innerHTML = '';
  document.querySelector('#trend-warning').textContent = error.message;
  document.querySelector('#trend-source').removeAttribute('href');
}

async function loadDistrict(slug) {
  document.querySelector('#district-name').textContent = 'Loading…';
  const [detail, trend] = await Promise.all([
    json(`/api/v1/districts/${slug}`),
    json(`/api/v1/districts/${slug}/trends/development-budget`).catch(error => ({ error })),
  ]);
  renderDistrict(detail);
  if (trend.error) renderTrendError(trend.error); else renderTrend(trend);
}

async function loadRankings() {
  const data = await json(`/api/v1/rankings?category=${rankingCategory.value}`);
  document.querySelector('#ranking-list').innerHTML = data.rankings.map(item => `
    <li class="${state.district?.slug === item.slug ? 'active' : ''}">
      <strong>${item.rank}</strong>
      <span>${escapeHtml(item.name)}<span class="bar-track"><span class="bar" style="display:block;width:${item.score}%"></span></span></span>
      <strong>${item.score}</strong>
    </li>`).join('');
}

async function askQuestion(question, districts = [state.district.slug]) {
  const answer = document.querySelector('#chat-answer');
  const submit = document.querySelector('#chat-form button');
  submit.disabled = true;
  answer.textContent = 'Searching structured facts and official evidence…';
  try {
    const data = await json('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, districts, session_id: state.sessionId }),
    });
    state.sessionId = data.session_id || state.sessionId;
    const citations = data.citations.map(citation =>
      `<li><a href="${safeUrl(citation.url)}" target="_blank" rel="noreferrer">${escapeHtml(citation.publisher)}: ${escapeHtml(citation.title)}</a> — ${escapeHtml(citation.period)} · ${escapeHtml(citation.locator)}</li>`
    ).join('');
    const warnings = data.warnings.map(warning => `<li>${escapeHtml(warning)}</li>`).join('');
    const tools = data.tools_used?.length ? `<span>tools: ${escapeHtml(data.tools_used.join(', '))}</span>` : '';
    const comparison = renderComparison(data.comparison);
    answer.innerHTML = `<div class="answer-meta"><span class="answer-mode mode-${data.mode}">${escapeHtml(data.mode)}</span><span>${escapeHtml(data.route)}</span>${tools}<span>trace ${escapeHtml(data.trace_id.slice(0, 8))}</span></div><p>${escapeHtml(data.answer)}</p>${comparison}${citations ? `<ol>${citations}</ol>` : ''}${warnings ? `<ul class="chat-warnings">${warnings}</ul>` : ''}`;
  } catch (error) {
    answer.innerHTML = `<p>Evidence service unavailable: ${escapeHtml(error.message)}</p>`;
  } finally {
    submit.disabled = false;
  }
}

async function init() {
  const data = await json('/api/v1/districts');
  state.districts = data.districts;
  select.innerHTML = data.districts.map(district => `<option value="${district.slug}">${escapeHtml(district.name)}</option>`).join('');
  await loadDistrict(data.districts[0].slug);
}

select.addEventListener('change', () => loadDistrict(select.value).catch(error => {
  document.querySelector('#notice').textContent = error.message;
}));
rankingCategory.addEventListener('change', () => loadRankings().catch(error => {
  document.querySelector('#ranking-list').innerHTML = `<li>${escapeHtml(error.message)}</li>`;
}));

document.querySelector('#scorecards').addEventListener('click', event => {
  const button = event.target.closest('[data-score-category]');
  if (!button) return;
  const category = button.dataset.scoreCategory;
  const question = `Why did ${state.district.name} receive its ${category} score?`;
  document.querySelector('#chat-question').value = question;
  askQuestion(question);
});

document.querySelector('#chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  await askQuestion(document.querySelector('#chat-question').value);
});

document.querySelectorAll('.chat-prompts button').forEach(button => {
  button.addEventListener('click', () => {
    const question = button.dataset.question.replace('this district', state.district.name);
    document.querySelector('#chat-question').value = question;
    askQuestion(question, button.dataset.allDistricts === 'true' ? [] : [state.district.slug]);
  });
});

init().catch(error => { document.querySelector('#notice').textContent = error.message; });
