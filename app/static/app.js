const state = { district: null, districts: [] };
const select = document.querySelector('#district-select');
const rankingCategory = document.querySelector('#ranking-category');

const number = (value, digits = 0) => Number(value).toLocaleString('en-PK', { maximumFractionDigits: digits });

async function json(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || data.error || 'Request failed');
  return data;
}

function card(title, score, rank, metrics, evidence) {
  return `<article class="score-card">
    <div class="score-top"><div><h3>${title}</h3><span class="rank">Rank ${rank.rank} of 5</span></div><strong class="score-number">${score}</strong></div>
    <ul class="metric-list">${metrics.map(([label, value]) => `<li><span>${label}</span><strong>${value}</strong></li>`).join('')}</ul>
    <a class="source-link" href="${evidence.citationUrl}" target="_blank" rel="noreferrer">View official source ↗</a>
  </article>`;
}

function renderDistrict(data) {
  state.district = data;
  document.querySelector('#notice').textContent = data.metadata.disclaimer;
  document.querySelector('#district-name').textContent = data.name;
  document.querySelector('#population').textContent = `Population ${number(data.population_2023)} · Census 2023`;
  document.querySelector('#overall-score').textContent = data.derived.scores.overall;
  document.querySelector('#overall-rank').textContent = `Rank ${data.rankings.overall.rank} of 5`;

  const educationSource = data.sources.pbs_table_12.url;
  const auditSource = data.sources.agp_dha.url;
  const education = data.education;
  const health = data.health;
  const accountability = data.accountability;
  document.querySelector('#scorecards').innerHTML = [
    card('Education', data.derived.scores.education, data.rankings.education, [
      ['Total literacy', `${number(education.literacy_total_pct, 1)}%`],
      ['Female literacy', `${number(education.literacy_female_pct, 1)}%`],
      ['Out-of-school age 5–16', number(education.out_of_school_children_5_16)],
    ], { citationUrl: educationSource }),
    card('Health access proxy', data.derived.scores.health, data.rankings.health, [
      ['Listed public facilities', number(data.derived.facility_count)],
      ['Facilities per 100k', number(data.derived.facilities_per_100k, 2)],
      ['BHUs / RHCs', `${number(health.bhus)} / ${number(health.rhcs)}`],
    ], { citationUrl: auditSource }),
    card('Financial management proxy', data.derived.scores.accountability, data.rankings.accountability, [
      ['Overall budget utilized', `${number(100 - accountability.overall_budget_lapse_pct, 1)}%`],
      ['Development budget utilized', `${number(100 - accountability.development_budget_lapse_pct, 1)}%`],
      ['Formations audited', `${accountability.audited_formations} of ${accountability.total_formations}`],
    ], { citationUrl: auditSource }),
  ].join('');
  loadRankings();
}

async function loadDistrict(slug) {
  renderDistrict(await json(`/api/v1/districts/${slug}`));
}

async function loadRankings() {
  const category = rankingCategory.value;
  const data = await json(`/api/v1/rankings?category=${category}`);
  document.querySelector('#ranking-list').innerHTML = data.rankings.map(item => `
    <li class="${state.district?.slug === item.slug ? 'active' : ''}">
      <strong>${item.rank}</strong>
      <span>${item.name}<span class="bar-track"><span class="bar" style="display:block;width:${item.score}%"></span></span></span>
      <strong>${item.score}</strong>
    </li>`).join('');
}

async function init() {
  const data = await json('/api/v1/districts');
  state.districts = data.districts;
  select.innerHTML = data.districts.map(district => `<option value="${district.slug}">${district.name}</option>`).join('');
  await loadDistrict(data.districts[0].slug);
}

select.addEventListener('change', () => loadDistrict(select.value));
rankingCategory.addEventListener('change', loadRankings);
async function askQuestion(question, allDistricts = false) {
  const answer = document.querySelector('#chat-answer');
  const submit = document.querySelector('#chat-form button');
  submit.disabled = true;
  answer.textContent = 'Searching structured facts and official evidence...';
  try {
    const data = await json('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, districts: allDistricts ? [] : [state.district.slug] }),
    });
    const citations = data.citations.map(citation =>
      `<li><a href="${citation.url}" target="_blank" rel="noreferrer">${citation.publisher}: ${citation.title}</a> — ${citation.locator}</li>`
    ).join('');
    const warnings = data.warnings.map(warning => `<li>${warning}</li>`).join('');
    answer.innerHTML = `<div class="answer-meta"><span class="answer-mode">${data.mode}</span><span>${data.route}</span></div><p>${data.answer}</p>${citations ? `<ol>${citations}</ol>` : ''}${warnings ? `<ul class="chat-warnings">${warnings}</ul>` : ''}`;
  } catch (error) {
    answer.innerHTML = `<p>Evidence service unavailable: ${error.message}</p>`;
  } finally {
    submit.disabled = false;
  }
}

document.querySelector('#chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  await askQuestion(document.querySelector('#chat-question').value);
});

document.querySelectorAll('.chat-prompts button').forEach(button => {
  button.addEventListener('click', () => {
    const question = button.dataset.question.replace('this district', state.district.name);
    document.querySelector('#chat-question').value = question;
    askQuestion(question, button.dataset.allDistricts === 'true');
  });
});

init().catch(error => { document.querySelector('#notice').textContent = error.message; });
