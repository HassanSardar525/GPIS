"""Evidence-only officeholder answers; no LLM arithmetic or causal attribution."""
import re
import uuid

from app.history import HistoryRepository, packaged_release
from app.schemas import AnswerMode, ChatResponse, Citation, QuestionRoute


def is_history_question(question):
    q = question.casefold()
    terms = packaged_release()['terms']
    return bool(re.search(r'\b(tenure|officeholders?|time in office|held office|chief ministers?|mpas?|representatives?|politicians?|ministers?)\b', q)) or any(
        t['person'] and len(t['person'].split()) > 1 and
        (t['person'].casefold() in q or (t['role'] == 'Chief minister' and any(n in q.split() for n in t['person'].casefold().split() if n not in {'muhammad','sharif','shahbaz','hasan'})))
        for t in terms)


def history_answer(request, repository):
    from app.routing import requires_abstention
    if not is_history_question(request.question) or requires_abstention(request.question):
        return None
    store = HistoryRepository(repository.name, getattr(repository, 'database_url', None))
    data = store.data()
    q = request.question.casefold()
    if re.search(r'\b(corrupt|stole|criminal|steal|caused|blame)\b', q):
        return ChatResponse(answer='These records cannot establish personal wrongdoing or causation. They can show sourced officeholding and measured district changes.', mode=AnswerMode.ABSTAINED,route=QuestionRoute.TENURE_HISTORY,citations=[],warnings=['No evidence supports that personal allegation.'],trace_id=str(uuid.uuid4()),abstained=True,model='deterministic-history',session_id=request.session_id)
    districts = request.selected_districts()
    for slug in districts:
        repository.get_district(slug)
    terms = store.officeholders(districts[0])['terms'] if districts else [t for t in data['terms'] if not t['districts']]
    named = [t for t in terms if t['person'] and (t['person'].casefold() in q or
             (t['role'] == 'Chief minister' and any(n in q.split() for n in t['person'].casefold().split() if n not in {'muhammad','sharif','shahbaz','hasan'})))]
    if named:
        terms = named
    elif re.search(r'\b(mpas?|representatives?)\b', q):
        terms = [t for t in terms if t['role']=='MPA']
    elif 'chief minister' in q:
        terms = [t for t in terms if t['role']=='Chief minister']
    elif 'minister' in q:
        terms = [t for t in terms if t['role']=='Provincial minister' and
                 (not any(w in q for w in ('health','education')) or any(w in (t['portfolio'] or '').lower() for w in ('health' if 'health' in q else 'education',)))]
    years = [int(y) for y in re.findall(r'\b20\d{2}\b', q)]
    if years:
        start, end = f'{min(years)}-01-01', f'{max(years)}-12-31'
        terms = [t for t in terms if not t['start'] or (t['start'] <= end and (t['end'] or t.get('verified_through') or '9999') >= start)]
    citations=[]
    def cite(aid):
        existing=next((i for i,c in enumerate(citations) if aid in c.anchor_ids),None)
        if existing is not None:return f'[{citations[existing].evidence_id}]'
        a=data['anchors'][aid]
        c=Citation(evidence_id=aid,source_id=a['source_id'],publisher=a['publisher'],title=a['title'],period=a['period'],url=a['url'],locator=a['locator'],passage=a['text'][:1800],anchor_ids=[aid])
        citations.append(c)
        return f'[{aid}]'
    lines=[]
    metric=None
    if any(w in q for w in ('change','improv','declin','performance','spending','budget','literacy','hospitals','bhus','dispensaries')):
        metric='literacy_total_pct' if any(w in q for w in ('literacy','education')) else 'dha_development_utilization_pct' if any(w in q for w in ('budget','utilization','spending')) else 'phs_bhus_count' if 'bhu' in q else 'phs_hospitals_count'
    if metric and districts:
        overlapping_ids=set()
        for slug in districts:
            # Exact selected-person comparisons require a unique reviewed term.
            selected=named[0]['id'] if len(named)==1 else None
            result=store.history(slug,metric,selected)
            comp=result['comparison']
            lines.append(f"{data['districts'][slug]['name']} — {result['metric_info']['label']}: {comp['label']}.")
            for note in sorted({r['reason'].split('Source conflict:',1)[1].strip()
                                for r in result['observations'] if 'Source conflict:' in r['reason']}):
                lines.append('Source conflict: '+note)
            if comp['change'] is not None:
                overlapping_ids.update(t['id'] for t in comp['officeholders'])
                lines.append(f"{comp['from']} to {comp['to']}: {comp['change']:+.3f} {comp['unit']}. "+' '.join(cite(a) for a in comp['anchor_ids']))
                lines.append('Overlapping reviewed officeholders: '+', '.join(t['person'] or 'Vacancy' for t in comp['officeholders'])+'.')
            else:
                lines.append(result['coverage']['reason'])
                for row in result['observations']:
                    lines.append(f"Available observation: {row['period']}, {row['value'] if row['value'] is not None else 'not reported'} {row['unit']}. "+' '.join(cite(a) for a in row['anchor_ids']))
        if not named and overlapping_ids:
            terms=[t for t in terms if t['id'] in overlapping_ids or not t['start']]
    elif metric:
        lines.append('Select a district to compare historical measurements during a tenure.')
    if not terms:
        lines.append('No matching reviewed officeholder record is available. This is a coverage gap, not evidence that the office was vacant.')
    for t in terms[:14]:
        dates=(t['start'] or 'start unverified')+' to '+(t['end'] or ('verified through '+t['verified_through'] if t.get('verified_through') else 'end unverified'))
        lines.append(f"{t['person'] or 'Vacancy'} — {t['role']}{' / '+t['portfolio'] if t['portfolio'] else ''}; {t['party'] or 'party not recorded'}{' (caretaker)' if t['caretaker'] else ''}; {dates}. "+' '.join(cite(a) for a in t['anchor_ids']))
        if t['status']!='verified' or named:
            lines.append(' '.join(t['notes']))
    if len(terms)>14:lines.append('Additional archived representatives are listed in the district profile; dates remain under review.')
    lines.append('These are district observations, not constituency outcomes or evidence of personal causation. Missing dates/years are not inferred; fiscal-year spending is not divided across administrations. Officeholder coverage is incomplete.')
    return ChatResponse(answer='\n\n'.join(lines),mode=AnswerMode.EXTRACTIVE,route=QuestionRoute.TENURE_HISTORY,
        citations=citations,warnings=['Officeholder coverage and historical comparisons are partial; inspect the source/date notes.'],
        trace_id=str(uuid.uuid4()),abstained=not bool(citations),model='deterministic-history',tools_used=['historical_records'],session_id=request.session_id)
