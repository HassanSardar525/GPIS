/* Dated observations, officeholders and packaged original-source evidence. */
let historicalRequest = 0;
let historicalMetric = 'phs_hospitals_count';
let historicalTenure = '';
let historicalSlug = '';
let evidenceRequest = 0;
let evidenceData = null;
let evidencePage = 0;
let evidenceOpener = null;

function evidenceButtons(ids = [], label = 'View evidence') {
  return ids.map((id, i) => `<button type="button" class="evidence-link" data-evidence="${escapeHtml(id)}">${escapeHtml(label)}${ids.length > 1 ? ` ${i + 1}` : ''}</button>`).join(' ');
}

function renderAnswerWithEvidence(answer, citations = []) {
  const map = new Map(citations.map((c,i) => [c.evidence_id, {citation:c, number:i+1}]));
  return escapeHtml(answer).replace(/\[([A-Za-z0-9._:-]+)\]/g, (marker,id) => {
    const hit=map.get(id);
    if(!hit?.citation.anchor_ids?.length) return marker;
    return `<button type="button" class="evidence-link" data-evidence="${escapeHtml(hit.citation.anchor_ids[0])}" aria-label="Open source ${hit.number}">[${hit.number}]</button>`;
  }).replaceAll('\n','<br>');
}

function termDates(term) {
  const start = term.start ? `${term.start}${term.start_precision !== 'day' ? ' (date awaiting review)' : ''}` : 'Start date unverified';
  const end = term.end ? `${term.end}${term.end_precision !== 'day' ? ' (date awaiting review)' : ''}` : term.verified_through ? `record verified through ${term.verified_through}` : 'end date unverified';
  return `${start} → ${end}`;
}

async function loadHistoricalEvidence(slug, reset = false) {
  const container = document.querySelector('#historical-content');
  if (!container) return;
  if (reset || historicalSlug !== slug) historicalTenure = '';
  historicalSlug = slug;
  const token = ++historicalRequest;
  container.setAttribute('aria-busy', 'true');
  try {
    const [data, holders] = await Promise.all([
      json(`/api/v1/districts/${encodeURIComponent(slug)}/history?metric=${encodeURIComponent(historicalMetric)}${historicalTenure ? '&tenure=' + encodeURIComponent(historicalTenure) : ''}`),
      json(`/api/v1/districts/${encodeURIComponent(slug)}/officeholders`)
    ]);
    if (token !== historicalRequest) return;
    const category = data.metric_info.category;
    const metricSelect = document.querySelector('#historical-metric');
    metricSelect.innerHTML = Object.entries(data.metrics).filter(([,m]) => m.category === category).map(([key,m]) => `<option value="${key}">${escapeHtml(m.label)}</option>`).join('');
    metricSelect.value = historicalMetric;
    const comparison = data.district_comparison;
    const overlapNames = (comparison.officeholders || []).map(t => (t.person || 'Vacancy') + (t.status !== 'verified' ? ' (dates awaiting review)' : '')).join(', ');
    const selected = holders.terms.find(t => t.id === historicalTenure);
    const points = data.observations.filter(o => o.value !== null);
    const minDate = Math.min(...points.map(o => Date.parse(o.start)), Date.parse('2017-01-01'));
    const maxDate = Math.max(...points.map(o => Date.parse(o.end)), Date.parse('2026-10-27'));
    const x = value => 60 + 800 * (Date.parse(value) - minDate) / (maxDate - minDate);
    const max = Math.max(1, ...points.map(o => o.value));
    const y = value => 190 - 150 * value / max;
    const selectionBand = selected?.start && (selected.end || selected.verified_through) ? `<rect x="${Math.max(60,x(selected.start))}" y="20" width="${Math.max(0,x(selected.end || selected.verified_through)-Math.max(60,x(selected.start)))}" height="180" class="tenure-band"/>` : '';
    const chart = points.length ? `<svg viewBox="0 0 920 245" role="img" aria-label="Dated observations; no interpolated values. Exact values and evidence links follow in the table.">
      ${selectionBand}<line x1="60" y1="200" x2="860" y2="200" stroke="currentColor"/>
      <text x="5" y="40">${number(max,1)}</text><text x="25" y="195">0</text>
      ${points.map(o => `<g><line x1="${x(o.start)}" y1="${y(o.value)}" x2="${x(o.end)}" y2="${y(o.value)}" class="observation-interval"/><circle cx="${x(o.end)}" cy="${y(o.value)}" r="7" class="history-point ${o.within_selected_tenure ? 'selected-point' : ''}" role="button" tabindex="0" data-evidence="${escapeHtml(o.anchor_ids[0])}" aria-label="${escapeHtml(o.period)}: ${number(o.value,3)}. Open evidence."/><title>${escapeHtml(o.period)}: ${number(o.value,3)}</title></g>`).join('')}
      ${[2017,2019,2021,2023,2025].map(year => `<text x="${x(year+'-01-01')}" y="230">${year}</text>`).join('')}
      </svg>` : '<p>No observations are available for this metric.</p>';
    const executives = holders.terms.filter(t => t.responsibility === 'provincial_executive');
    const representatives = holders.terms.filter(t => t.responsibility === 'constituency_representation');
    function termCard(t) {
      const eligible = data.comparable_tenures.includes(t.id);
      const startsBetween = comparison.change !== null && t.start_precision === 'day' &&
        comparison.start < t.start && t.start <= comparison.end;
      const qualification = startsBetween ? `Took office on ${escapeHtml(t.start)}, after the first measurement began on ${escapeHtml(comparison.start)}.` : '';
      return `<li class="officeholder ${historicalTenure === t.id ? 'selected-tenure' : ''}">
        <strong>${escapeHtml(t.person || 'Vacancy')}</strong>
        ${eligible ? `<button type="button" data-tenure="${escapeHtml(t.id)}" aria-pressed="${historicalTenure === t.id}">Compare this term</button>` : ''}
        ${qualification ? `<p>${qualification}</p>` : ''}
        <p>${escapeHtml(t.role)} · ${escapeHtml(t.constituency || 'Punjab province')}${t.portfolio ? ' · '+escapeHtml(t.portfolio) : ''} · ${escapeHtml(t.party || 'Party not recorded')}${t.caretaker ? ' · Caretaker' : ''}</p>
        <p>${escapeHtml(termDates(t))}</p>
        ${t.constituency ? `<p>${escapeHtml(t.constituency)} · ${escapeHtml(t.boundary_edition)}</p>` : ''}
        <details><summary>${t.status === 'verified' ? 'Source and date notes' : 'Incomplete record — review notes'}</summary><p>${escapeHtml(t.notes.join(' '))}</p>${evidenceButtons(t.anchor_ids)}</details>
      </li>`;
    }
    const unit = {percent: '%', count: '', million_pkr: ' Rs million'}[data.metric_info.unit] ?? ' ' + escapeHtml(data.metric_info.unit);
    const precision = {percent: 2, count: 0, million_pkr: 3}[data.metric_info.unit] ?? 2;
    const disputed = data.observations.find(o => o.reason.startsWith('Source conflict:') || o.reason.startsWith('Utilization withheld:'));
    const gap = disputed ? disputed.reason : !points.length ? 'No reviewed figure for this measure.' :
      category === 'education' && points.length === 1 ? 'An earlier comparable literacy figure is awaiting review.' :
      points.length < 2 ? 'Only one measured period is available.' :
      'The reporting boundaries and definitions still need a cross-year check.';
    container.innerHTML = `<div class="history-readings">${data.observations.map(o => `<div>
      <span>${escapeHtml(o.period)}</span><strong>${o.value === null ? 'Not reported' : number(o.value, precision) + unit}</strong>
      ${evidenceButtons(o.anchor_ids, 'View source')}</div>`).join('')}</div>
      <div class="history-result" role="status">${comparison.change !== null ?
        `<strong>District change: ${comparison.change > 0 ? '+' : ''}${number(comparison.change,precision)} ${escapeHtml(comparison.unit.replace('million_pkr','Rs million'))}</strong>
        <p>${escapeHtml(comparison.label)} · ${escapeHtml(overlapNames)}</p>` : escapeHtml(gap)}</div>
      ${selected && data.comparison.change !== null ? `<p>${escapeHtml(selected.person)} · Change within this term: ${number(data.comparison.change,precision)} ${escapeHtml(data.comparison.unit)}</p><button type="button" data-tenure="">Clear tenure selection</button>` : ''}
      <details class="history-detail"><summary>Chart and measurement details</summary>
      <div class="history-chart">${chart}</div>
      <div class="table-scroll"><table class="comparison-table"><caption>${escapeHtml(data.metric_info.label)} — measured dates, not publication dates</caption><thead><tr><th>Observation period</th><th>Value</th><th>Administrations overlapping this period</th><th>Evidence</th></tr></thead><tbody>
      ${data.observations.map(o => `<tr class="${o.within_selected_tenure ? 'selected-tenure' : ''}"><th>${escapeHtml(o.period)}<small>${escapeHtml(o.start)} to ${escapeHtml(o.end)} (${escapeHtml(o.date_precision)})</small></th><td>${o.value === null ? 'Not reported' : number(o.value,3)}</td><td>${escapeHtml(holders.terms.filter(t => o.officeholders.includes(t.id)).map(t => t.person).join(', ') || 'Verified date coverage unavailable')}<small>${escapeHtml(o.reason)}</small></td><td>${evidenceButtons(o.anchor_ids)}</td></tr>`).join('')}
      </tbody></table></div>
      <p>${escapeHtml(data.notice)}</p></details>
      <details><summary>Provincial officeholders and term dates</summary>
      <ol class="officeholder-timeline">${executives.map(termCard).join('')}</ol></details>
      <details><summary>Historical representation · 2018 Assembly, published 2021 (${representatives.length} archived records)</summary><p>${escapeHtml(holders.coverage.mpas)}</p><p>${escapeHtml(holders.notice)}</p><ul class="officeholder-timeline">${representatives.map(termCard).join('') || '<li>No reviewed representation records yet.</li>'}</ul></details>
      <p class="history-coverage">${escapeHtml(holders.coverage.ministers)}</p>
      ${evidenceButtons(['calculated-'+slug], 'How this district’s scores are calculated')}`;
  } catch (error) {
    if (token === historicalRequest) container.innerHTML = `<p role="alert">Historical evidence could not load: ${escapeHtml(error.message)}</p><button type="button" data-history-retry>Retry</button>`;
  } finally {
    if (token === historicalRequest) container.setAttribute('aria-busy','false');
  }
}

function renderEvidencePage(focusHighlight = true) {
  const area = document.querySelector('#evidence-document');
  if (!evidenceData) return;
  const pages = evidenceData.pages || [];
  const pg = pages[evidencePage];
  const zoom = Number(document.querySelector('#evidence-zoom').value);
  document.querySelector('#evidence-controls').hidden = !pg;
  document.querySelector('#evidence-prev').disabled = evidencePage === 0;
  document.querySelector('#evidence-next').disabled = evidencePage >= pages.length - 1;
  document.querySelector('#evidence-page-label').textContent = pg ? `PDF page ${pg.number}${pg.printed_label ? ` · printed page ${pg.printed_label}` : ''} · packaged page ${evidencePage+1}/${pages.length}` : 'Source details';
  if (pg) {
    area.innerHTML = `<div class="evidence-page-image" style="width:${zoom}%"><img src="${escapeHtml(pg.asset_url)}" alt="Original full document page ${pg.number}. Accessible text follows."/>
      ${pg.rectangles.map(b => `<span class="evidence-highlight" aria-hidden="true" style="left:${b[0]*100}%;top:${b[1]*100}%;width:${(b[2]-b[0])*100}%;height:${(b[3]-b[1])*100}%"></span>`).join('')}</div>`;
    document.querySelector('#evidence-text').textContent = pg.text;
    const img = area.querySelector('img');
    const position = () => {
      const box = pg.rectangles.at(-1);
      area.scrollTop = focusHighlight && box ? Math.max(0, img.clientHeight * box[1] - area.clientHeight * .25) : 0;
      area.scrollLeft = 0;
    };
    img.addEventListener('load', position, {once:true});
    if (img.complete) position();
  } else if (evidenceData.kind === 'spreadsheet') {
    area.innerHTML = (evidenceData.worksheets || []).map(sheet => `<h3>${escapeHtml(sheet.name)} · ${escapeHtml(sheet.ranges.join(', '))}</h3><div class="table-scroll"><table class="evidence-sheet"><caption>Original worksheet cells and headings</caption><tbody>${sheet.rows.map(row => '<tr>'+row.map(cell => `<td class="${cell.highlight ? 'highlight-cell' : ''}"><small>${escapeHtml(cell.address)}</small>${escapeHtml(cell.value ?? '')}</td>`).join('')+'</tr>').join('')}</tbody></table></div>`).join('');
    document.querySelector('#evidence-text').textContent = evidenceData.text;
  } else {
    area.innerHTML = `<p>${escapeHtml(evidenceData.text)}</p>`;
    document.querySelector('#evidence-text').textContent = evidenceData.text;
  }
}

async function openEvidence(id, bookmark = true) {
  const dialog = document.querySelector('#evidence-panel');
  const token = ++evidenceRequest;
  if (!dialog.open) { evidenceOpener = document.activeElement; dialog.showModal(); }
  if (bookmark) {
    const [path,query] = location.hash.split('?');
    const params = new URLSearchParams(query || ''); params.set('evidence',id);
    history.pushState(null,'',`${path || '#/overview'}?${params}`);
  }
  evidenceData = null;
  document.querySelector('#evidence-controls').hidden = true;
  document.querySelector('#evidence-official').hidden = true;
  document.querySelector('#evidence-locator').textContent = '';
  document.querySelector('#evidence-status').textContent = '';
  document.querySelector('#evidence-title').textContent = 'Loading evidence…';
  document.querySelector('#evidence-document').innerHTML = '';
  document.querySelector('#evidence-text').textContent = '';
  document.querySelector('#evidence-support').innerHTML = '';
  try {
    const data = await json('/api/v1/evidence/'+encodeURIComponent(id));
    if (token !== evidenceRequest) return;
    evidenceData=data; evidencePage=0;
    document.querySelector('#evidence-zoom').value='100';
    document.querySelector('#evidence-title').textContent=data.title;
    document.querySelector('#evidence-locator').textContent=`${data.publisher} · ${data.period} · ${data.locator}`;
    document.querySelector('#evidence-status').textContent = data.highlight_status === 'verified' ? 'Verified source location highlighted. Full-page context is preserved.' : data.kind === 'webpage' ? 'Reviewed source summary. Open the official page for the original wording; no page highlight is claimed.' : data.kind === 'calculated' ? 'Calculated result. Inspect the methodology and supporting input evidence below.' : 'Exact highlight unavailable. Showing the registered page or original source link.';
    const link=document.querySelector('#evidence-official'); link.href=safeUrl(data.url); link.hidden=link.getAttribute('href')==='#';
    document.querySelector('#evidence-support').innerHTML=evidenceButtons(data.supporting_anchor_ids,'Inspect input evidence');
    renderEvidencePage();
  } catch (error) {
    if(token!==evidenceRequest)return;
    evidenceData=null;
    document.querySelector('#evidence-title').textContent='Evidence unavailable';
    const status = document.querySelector('#evidence-status');
    status.textContent = error.message + ' ';
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.textContent = 'Retry evidence';
    retry.onclick = () => openEvidence(id, false);
    status.append(retry);
    document.querySelector('#evidence-official').hidden=true;
  }
}

function restoreEvidenceBookmark() {
  const id=new URLSearchParams(location.hash.split('?')[1] || '').get('evidence');
  if(id) openEvidence(id,false);
  else if(document.querySelector('#evidence-panel').open) document.querySelector('#evidence-panel').close();
}
const profileHistoryPanel = document.querySelector('#performance-history');
let profileHistoryOpener;
window.closeProfileHistory = function () {
  ++historicalRequest;
  profileHistoryPanel.hidden = true;
  document.querySelector('#scorecards').after(profileHistoryPanel);
};
document.querySelector('#close-profile-history').addEventListener('click', () => {
  window.closeProfileHistory();
  profileHistoryOpener?.focus();
});

document.addEventListener('click',event=>{
  const evidence=event.target.closest('[data-evidence]');
  if(evidence){event.preventDefault();openEvidence(evidence.dataset.evidence);return;}
  const term=event.target.closest('[data-tenure]');
  if(term){historicalTenure=term.dataset.tenure;loadHistoricalEvidence(historicalSlug);}
  const metric = event.target.closest('[data-profile-history]');
  if (metric) {
    profileHistoryOpener = metric;
    metric.closest('.profile-more').append(profileHistoryPanel);
    profileHistoryPanel.hidden = false;
    historicalMetric = metric.dataset.profileHistory;
    document.querySelector('#historical-content').textContent = 'Loading reviewed historical evidence…';
    loadHistoricalEvidence(state.district.slug, true);
    document.querySelector('#historical-metric').focus();
  }
  if(event.target.closest('[data-history-retry]'))loadHistoricalEvidence(historicalSlug);
});
document.addEventListener('keydown',event=>{
  if(['Enter',' '].includes(event.key) && event.target.matches('circle[data-evidence]')) {event.preventDefault();openEvidence(event.target.dataset.evidence);}
});
document.querySelector('#historical-metric').addEventListener('change',event=>{historicalMetric=event.target.value;loadHistoricalEvidence(historicalSlug,true);});
document.querySelector('#evidence-close').addEventListener('click',()=>document.querySelector('#evidence-panel').close());
document.querySelector('#evidence-panel').addEventListener('close',()=>{
  ++evidenceRequest;
  const [path,query]=location.hash.split('?');const params=new URLSearchParams(query||'');params.delete('evidence');
  history.replaceState(null,'',path+(params.size?'?'+params:''));
  evidenceOpener?.focus();
});
document.querySelector('#evidence-zoom').addEventListener('input',renderEvidencePage);
document.querySelector('#evidence-full-page').addEventListener('click',()=>{document.querySelector('#evidence-zoom').value='100';renderEvidencePage(false);});
document.querySelector('#evidence-prev').addEventListener('click',()=>{if(evidencePage>0){evidencePage--;renderEvidencePage();}});
document.querySelector('#evidence-next').addEventListener('click',()=>{if(evidencePage<evidenceData.pages.length-1){evidencePage++;renderEvidencePage();}});
window.addEventListener('hashchange',restoreEvidenceBookmark);
restoreEvidenceBookmark();
