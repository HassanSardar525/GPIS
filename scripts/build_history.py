"""Build the reviewed historical release and pre-render registered source pages.

Run offline after acquiring the source files listed in the curated contracts.
No model-generated text is searched for or used as an exact source quotation.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.history import ROOT, validate_release

CURATED = ROOT / 'data/curated'
ASSETS = ROOT / 'data/evidence'


def read(name):
    return json.loads((CURATED / (name + '.json')).read_text(encoding='utf8'))


def build():
    import openpyxl
    import pdfplumber
    import pypdfium2

    current, old, services, health = [read(n) for n in ('punjab_districts', 'districts', 'punjab_services', 'health_capacity_periods')]
    sources = {**old['sources'], **services['sources'], **current['sources']}
    for key, value in health['sources'].items():
        sources[key] = {**value, 'url': value['official_url'], 'period': value['period_label']}
    sources['pap_biographies_2021'] = {'title': 'Punjab Assembly biographies, 2018 assembly; published 2021',
        'publisher': 'Provincial Assembly of the Punjab', 'period': '2021 publication snapshot',
        'url': 'https://www.pap.gov.pk/uploads/downloads/biography-members-2018-23.pdf',
        'local_file': 'data/raw/pap_members_2018_23.pdf'}
    for s in sources.values():
        if s.get('local_file') and (ROOT / s['local_file']).is_file():
            digest = hashlib.sha256((ROOT / s['local_file']).read_bytes()).hexdigest()
            if s.get('sha256') and s['sha256'] != digest:
                raise ValueError(f"Source checksum changed: {s['local_file']}")
            s['sha256'] = digest
    anchors, index, observations, terms = {}, {}, [], []
    ASSETS.mkdir(parents=True, exist_ok=True)
    pdfs, renders, books = {}, {}, {}
    reviewed_path = CURATED / 'evidence_highlights.json'
    highlights = json.loads(reviewed_path.read_text()) if reviewed_path.exists() else {}

    def anchor(source_id, locator, evidence_id=None, preview=True):
        source = sources[source_id]
        identity = (source.get('sha256', source_id) + '|' + locator)
        aid = 'ev-' + hashlib.sha256(identity.encode()).hexdigest()[:20]
        index[source_id + '|' + locator] = [aid]
        if evidence_id:
            index[evidence_id] = [aid]
        if aid in anchors:
            return aid
        a = {'id': aid, 'source_id': source_id, 'title': source['title'], 'publisher': source['publisher'],
             'period': source.get('period', ''), 'url': source['url'], 'locator': locator,
             'checksum': source.get('sha256'), 'kind': 'webpage', 'pages': [], 'text': '',
             'highlight_status': 'unavailable', 'supporting_anchor_ids': []}
        filename = source.get('local_file', '')
        if filename.endswith('.pdf'):
            a['kind'] = 'pdf'
            numbers = sorted(set(int(n) for n in re.findall(r'PDF page (\d+)', locator, re.I)))
            a['pdf_pages'] = numbers
            if numbers:
                a['url'] = source['url'].split('#')[0] + '#page=' + str(numbers[0])
            printed = re.findall(r'printed page (\d+)', locator, re.I)
            a['printed_page_labels'] = printed
            if preview and numbers:
                if filename not in pdfs:
                    pdfs[filename] = pdfplumber.open(ROOT / filename)
                    renders[filename] = pypdfium2.PdfDocument(ROOT / filename)
                for number in numbers:
                    pg = pdfs[filename].pages[number - 1]
                    asset = source['sha256'][:16] + '-' + str(number) + '.png'
                    if not (ASSETS / asset).exists():
                        bitmap = renders[filename][number - 1].render(scale=1.5)
                        bitmap.to_pil().save(ASSETS / asset, optimize=True)
                        bitmap.close()
                    review = highlights.get(aid, {}).get(str(number), {})
                    if source_id == 'punjab_health_statistics_2024':
                        name_match = re.search(r'Table 3, (.*?) District row', locator)
                        if name_match:
                            for word in pg.extract_words():
                                if word['text'] != 'District' or word['x0'] >= 172 or word['top'] < 145:
                                    continue
                                chars = [c for c in pg.chars if abs(c['top']-word['top']) < 1]
                                name = ''.join(c['text'] for c in sorted(chars,key=lambda c:c['x0']) if c['x0']<172).replace(' District','').strip()
                                if name == name_match[1]:
                                    review = {'rectangles': [[52/pg.width,(word['top']-2)/pg.height,556/pg.width,(word['bottom']+2)/pg.height]],
                                              'review':'Original district row and headings visually reviewed across Table 3 pages 19–23 on 27 October 2026.'}
                                    break
                    a['pages'].append({'number': number, 'printed_label': printed[0] if len(printed) == 1 else None,
                        'asset': asset, 'asset_sha256': hashlib.sha256((ASSETS / asset).read_bytes()).hexdigest(), 'rectangles': review.get('rectangles', []),
                        'text': review.get('text', pg.extract_text() or 'Scanned page. See the reviewed transcription and original full-page image.'),
                        'review': review.get('review', 'Verified source page; exact highlight not yet reviewed.')})
                a['highlight_status'] = 'verified' if any(p['rectangles'] for p in a['pages']) else 'page_only'
                a['text'] = '\n\n'.join(p['text'] for p in a['pages'])
            else:
                a['text'] = 'Original source page is registered. A packaged preview/highlight is not available; use the official document link.'
        elif filename.endswith('.xlsx'):
            a['kind'] = 'spreadsheet'
            if filename not in books:
                books[filename] = openpyxl.load_workbook(ROOT / filename, data_only=True)
            matches = re.findall(r'(?:;\s*)([^;!]+)!([A-Z]+\d+(?::[A-Z]+\d+)?)', locator)
            a['worksheets'] = []
            for sheet in dict.fromkeys(m[0].strip() for m in matches):
                ws = books[filename][sheet]
                addresses = set()
                for sh, cells in matches:
                    if sh.strip() == sheet:
                        if ':' not in cells:
                            addresses.add(cells)
                        else:
                            for row in ws[cells]:
                                addresses.update(c.coordinate for c in row)
                nums = [ws[c].row for c in addresses]
                # Preserve original column letters, worksheet row numbers, headers,
                # and the district block surrounding each selected cell.
                rownums = set(range(1, 8))
                if source_id == 'pbs_table_12':
                    rownums = set(range(1, 5))
                for n in nums:
                    heading = next((r for r in range(n, max(0,n-25), -1)
                        if 'DISTRICT' in str(ws.cell(r,1).value or '') and ws.cell(r,2).value is None), max(1,n-3))
                    rownums.update(range(heading, min(ws.max_row,n+2)+1))
                rownums = sorted(rownums)
                rows = [[{'address': ws.cell(r,c).coordinate, 'value': ws.cell(r,c).value,
                          'highlight': ws.cell(r,c).coordinate in addresses} for c in range(1, min(ws.max_column, 12)+1)] for r in rownums]
                a['worksheets'].append({'name': sheet, 'ranges': [m[1] for m in matches if m[0].strip()==sheet], 'rows': rows})
            a['highlight_status'] = 'verified'
            a['text'] = 'Original worksheet values, row numbers and column letters; highlighted cells match the registered extraction addresses.'
        else:
            a['text'] = 'Reviewed source register entry. Open the official source for the original document.'
        anchors[aid] = a
        return aid

    # Citation enrichment covers the existing district, chat and trend contracts.
    for dataset in (current, old):
        for d in dataset['districts']:
            for e in d['evidence']:
                anchor(e['source_id'], e['locator'], e['id'])
        for e in dataset.get('project_evidence', []):
            if e['source_id'] in sources:
                aid = anchor(e['source_id'], e['locator'], e['id'], preview=False)
                if 'method' in e['id']:
                    anchors[aid].update(kind='calculated', text=e['text'], highlight_status='not_applicable')

    metrics = {
        'literacy_total_pct': {'label': 'Literacy, ages 10+', 'category': 'education', 'unit': 'percent'},
        **{f'phs_{f}_count': {'label': label, 'category': 'health', 'unit': 'count'} for f,label in
           [('hospitals','Public hospitals'),('dispensaries','Dispensaries'),('rhcs','Rural health centres'),('bhus','Basic health units')]},
        **{f'dha_{kind}_{measure}_million_pkr': {'label': f'DHA {kind} {measure} (nominal Rs million)', 'category': 'spending', 'unit': 'million_pkr'}
           for kind in ('total','development') for measure in ('budget','expenditure')},
        'dha_development_utilization_pct': {'label': 'DHA development utilization', 'category': 'spending', 'unit': 'percent'},
    }
    pilot = {d['slug'] for d in old['districts']}
    south = ['bahawalnagar','bahawalpur','chiniot','dera-ghazi-khan','faisalabad','jhang','khanewal','layyah','lodhran','multan','muzaffargarh','pakpattan','rahim-yar-khan','rajanpur','sahiwal','toba-tek-singh','vehari']

    def observation(d, o, comparable=None, reason='', aid=None):
        if o['metric_key'] not in metrics:
            return
        period = o['period']
        if period.startswith('FY '):
            year = int(period[3:7]); start, end, precision = f'{year}-07-01', f'{year+1}-06-30', 'fiscal_year'
        elif len(period) == 4:
            start, end, precision = period+'-01-01', period+'-12-31', 'year'
        else:
            start = end = period; precision = 'day'
        aid = aid or anchor(o['source_id'], o['locator'])
        row = {'id': d['slug']+'-'+o['metric_key']+'-'+period.replace(' ','-'),
               'district': d['slug'], 'metric': o['metric_key'], 'value': o['value'], 'unit': o['unit'],
               'start': start, 'end': end, 'date_precision': precision, 'period': period,
               'definition': o['metric_key']+'-v1', 'population_group': 'ages 10+' if o['metric_key']=='literacy_total_pct' else 'registered public institutions / district health authority',
               'geography': 'Census-2023-district:'+d['slug'], 'comparability': comparable,
               'status': 'verified', 'reason': reason, 'anchor_ids': [aid]}
        observations.append(row)

    for d in current['districts']:
        for o in d['observations']:
            if o['metric_key'] in metrics:
                # Development series for pilot districts comes from the report's
                # explicit two-year comparison rather than mixing chapter totals.
                if d['slug'] in south and o['metric_key'].startswith('dha_development_'):
                    continue
                group = 'phs-table-3-v1' if o['metric_key'].startswith('phs_') else None
                observation(d,o,group, 'Measurement verified; historical comparability requires separately reviewed matching geography and definitions.' if not group else 'Existing reviewed Table 3 comparison; reported capacity, not outcomes.')
    for d in services['districts']:
        for o in d['observations']:
            if o['period']=='FY 2022-23':
                observation(d,o,None,'North DHA historical figure verified. Cross-year administrative boundaries/definitions await review; no change is calculated.')
    manual = read('health_history_review')
    assert manual['sha256'] == sources[manual['source_id']]['sha256']
    for row in manual['rows']:
        slug = row['district']; page = row['pdf_page']
        locator = f"Table 3; {slug} district row; PDF page {page}; printed page {row['printed_page']}"
        aid = anchor(manual['source_id'],locator)
        a=anchors[aid]; a['highlight_status']='verified'
        a['pages'][0]['rectangles']=[row['rectangle']]
        a['text']=a['pages'][0]['text']=f"Reviewed transcription, {slug}, as on 01-01-2023: "+'; '.join(f'{k}: {v} institutions' for k,v in row['counts'].items())+'. '+manual['review']
        a['pages'][0]['review']='Manual original-image row review, 27 October 2026.'
        for f,value in row['counts'].items():
            observation({'slug':slug},dict(metric_key=f'phs_{f}_count',value=value,unit='count',period='2023-01-01',source_id=manual['source_id'],locator=locator), 'phs-table-3-v1',manual['review'],aid)
    # Re-extract the explicit comparative table. Never silently copy a legacy
    # number when the printed table differs (Multan final grant differs by .001m).
    sid='agp_dha_development_comparison'
    with pdfplumber.open(ROOT/sources[sid]['local_file']) as pdf:
        table=pdf.pages[25].extract_tables()[0]
        assert len(table)==21 and 'FY 2022-23' in str(table[:3]) and 'FY 2023-24' in str(table[:3])
        for i,slug in enumerate(south):
            row=table[i+3]; assert row[0]==str(i+1)
            d={'slug':slug}
            locator=f'PDF page 26 (printed page 15), row {i+1}'
            aid=anchor(sid,locator)
            # Header and district row, verified against the full-page image.
            anchors[aid]['highlight_status']='verified'
            anchors[aid]['pages'][0]['rectangles']=[[149/894,125/1263,746/894,203/1263],[149/894,(203+i*22.45)/1263,746/894,(225.45+i*22.45)/1263]]
            anchors[aid]['pages'][0]['review']='Comparative table header, row identity and final-grant/expenditure columns visually reviewed, 27 October 2026.'
            for period,cols in [('FY 2022-23',(3,5)),('FY 2023-24',(7,9))]:
                budget,spent=[float(row[c].replace(',','')) for c in cols]
                for key,value,unit in [('dha_development_budget_million_pkr',budget,'million_pkr'),('dha_development_expenditure_million_pkr',spent,'million_pkr'),('dha_development_utilization_pct',100*spent/budget if budget else None,'percent')]:
                    reason='Explicit two-year comparative table for the same district health authority. Nominal amounts; no apportioning between administrations.'
                    if slug=='multan':reason+=' Source conflict: comparative table final grant is 1013.030m; existing score input is 1013.029m. Historical series follows this table; scores are unchanged.'
                    observation(d,dict(metric_key=key,value=value,unit=unit,period=period,source_id=sid,locator=locator),'agp-south-comparative-development-v1',reason,aid)

    # Cross-check the North report's explicit two-year tables against both district chapters.
    sid = 'agp_dha_north_budget_2023_24'
    periods = ('FY 2022-23', 'FY 2023-24')
    north = {d['slug'] for d in current['districts']} - set(south)
    chapter = {(r['district'], r['period'], r['metric']): r for r in observations if r['district'] in north}
    with pdfplumber.open(ROOT / sources[sid]['local_file']) as pdf:
        for measure, parts in [('budget', [(22, 1), (23, 0)]), ('expenditure', [(23, 1), (24, 0)])]:
            metric = f'dha_development_{measure}_million_pkr'
            totals = [Decimal(0), Decimal(0)]
            seen = set()
            for page_number, table_index in parts:
                table = pdf.pages[page_number - 1].extract_tables()[table_index]
                assert table[0][2::2] == list(periods)
                heading = 'Final Grant' if measure == 'budget' else 'Expenditure'
                assert all(table[1][c].replace('\n', ' ') == heading for c in (3, 5))
                for row in table[2:]:
                    values = [Decimal(row[c].replace(',', '')) for c in (3, 5)]
                    if row[0] == 'Total':
                        assert values == totals and seen == north
                        continue
                    slug = row[1].lower().replace(' ', '-')
                    assert slug in north and slug not in seen
                    seen.add(slug)
                    locator = f'{heading}, {row[1]}, row {row[0]}; PDF page {page_number} (printed page {page_number-18})'
                    aid = anchor(sid, locator)
                    for i, (period, value) in enumerate(zip(periods, values)):
                        totals[i] += value
                        record = chapter[slug, period, metric]
                        record['anchor_ids'].append(aid)
                        if Decimal(str(record['value'])) == value:
                            record['comparability'] = 'agp-north-comparative-development-v1'
                            record['reason'] = 'District chapter and two-year comparison table agree for this authority and period.'
                        else:
                            record['reason'] = (f"Source conflict: district chapter reports {record['value']:.3f} million; "
                                                f"comparative table reports {value:.3f} million. Change withheld.")
    for slug in sorted(north):
        for period in periods:
            budget = chapter[slug, period, 'dha_development_budget_million_pkr']
            spent = chapter[slug, period, 'dha_development_expenditure_million_pkr']
            supported = budget['comparability'] and spent['comparability'] and budget['value']
            observations.append({**budget, 'id': f"{slug}-dha_development_utilization_pct-{period.replace(' ', '-')}",
                'metric': 'dha_development_utilization_pct', 'definition': 'dha_development_utilization_pct-v1',
                'value': 100 * spent['value'] / budget['value'] if supported else None, 'unit': 'percent',
                'comparability': budget['comparability'] if supported else None,
                'status': 'verified' if supported else 'awaiting_review',
                'reason': 'Expenditure divided by final grant, multiplied by 100.' if supported else
                          'Utilization withheld: a source input is disputed or the denominator is zero.',
                'anchor_ids': list(dict.fromkeys(budget['anchor_ids'] + spent['anchor_ids']))})

    # Hand-reviewed official officeholder register, with provenance per event.
    office = read('officeholder_register')
    for source_id, source in office['sources'].items():
        sources[source_id] = source
        aid = anchor(source_id, source['locator'], preview=False)
        anchors[aid]['text'] = source['reviewed_excerpt']
        anchors[aid]['highlight_status'] = 'not_applicable'
    for t in office['terms']:
        record = {k:v for k,v in t.items() if k!='source_ids'}
        record['anchor_ids'] = [anchor(s,sources[s]['locator'],preview=False) for s in t['source_ids']]
        terms.append(record)

    # The Assembly's 2021 publication establishes names/party/constituency only.
    # Never fill actual service dates from an election year or publication date.
    pap = pdfplumber.open(ROOT / sources['pap_biographies_2021']['local_file'])
    slug_names = {d['name'].upper():d['slug'] for d in current['districts']}
    slug_names.update({'D.G. KHAN':'dera-ghazi-khan', 'D.G.KHAN':'dera-ghazi-khan', 'R.Y. KHAN':'rahim-yar-khan'})
    for n, pg in enumerate(pap.pages,1):
        text = pg.extract_text() or ''
        match = re.search(r'\n(PP-\d+)\s*\(([^)]+)\)\s*\n([^\n]+)\n(PTI|PML\s*\(N\)|PML\s*\(Q\)|PML|PPPP|IND|Independent)\s*\n', text)
        if not match:
            continue
        constituency, district_name, person, party = match.groups()
        slug = slug_names.get(district_name.strip())
        if not slug:
            continue
        footer = text.strip().splitlines()[-1]
        printed = f'; printed page {footer}' if footer.isdigit() else ''
        aid = anchor('pap_biographies_2021',f'PDF page {n}{printed}; {constituency} ({district_name}); name and party heading',preview=False)
        anchors[aid]['text'] = f'Reviewed heading: {constituency} ({district_name}); {person}; {party}. Publication: 2021. Actual office start/end dates are not established by this heading.'
        terms.append(dict(id='pap-2021-'+constituency.lower(), person=person.title(),role='MPA',responsibility='constituency_representation',portfolio=None,party=party,
            caretaker=False,vacancy=False,start=None,end=None,start_precision='unknown',end_precision='unknown',verified_through=None,
            status='awaiting_review',notes=['Listed in the 2021 Assembly biography for the 2018 assembly. Full service dates, later by-elections and party changes await notification review. Not a current-member claim.'],
            districts=[slug],constituency=constituency,boundary_edition='2018 assembly constituencies, as listed in the 2021 biography',mapping_anchor_ids=[aid],anchor_ids=[aid]))
    pap.close()

    districts = {}
    for d in current['districts']:
        coverage = {}
        for metric in metrics:
            rows = [r for r in observations if r['district']==d['slug'] and r['metric']==metric]
            valid = [r for r in rows if r['comparability'] and r['value'] is not None]
            coverage[metric] = {'status': 'verified' if len(valid)>1 else 'awaiting_review' if rows else 'unavailable',
                'reason': 'Comparable observations available.' if len(valid)>1 else 'No reviewed comparable pair. Older source definitions/geography or missing observations still need review.',
                'observations':len(rows), 'research_from':'2017'}
        districts[d['slug']] = {'name':d['name'], 'metrics':coverage, 'officeholders': {
            'chief_ministers': 'Official history with explicit handover/source notes; no claim of complete daily precision.',
            'ministers': 'Partial: reviewed caretaker portfolio appointments; remaining terms and portfolio changes await notifications.',
            'mpas': 'Partial 2021 biography snapshot. Actual service dates, vacancies and by-elections await review.',
            'status':'awaiting_review'}}
    result = dict(version='history-v1', reviewed_on='2026-11-26', research_from='2017', sources=sources,
        source_register=office['source_register'],metrics=metrics,districts=districts,terms=terms,
        observations=observations,anchors=anchors,citation_index=index)
    # Scores are calculated, never a quoted source statistic. Link their input evidence.
    for d in current['districts']:
        aid = 'calculated-'+d['slug']
        anchors[aid] = dict(id=aid,kind='calculated',title='GPIS calculated scores: '+d['name'],publisher='GPIS',period='punjab-v1',url='/#/district/'+d['slug'],locator='docs/PUNJAB_SCORING.md',checksum=None,pages=[],highlight_status='not_applicable',
            text='Calculated result, not a government rating. Education: mean of total literacy, female literacy and 100 minus gender gap. Health: four public institution categories per 100,000 population, min–max normalized across 36 districts. DHA spending: mean of overall and development utilization, each clamped to 0–100. Overall: equal mean of the three scores. This is not a politician score.',
            supporting_anchor_ids=[index[e['id']][0] for e in d['evidence'] if e['category'] in ('education','context','health','accountability')])
    validate_release(result)
    for p in pdfs.values(): p.close()
    for p in renders.values(): p.close()
    return result


if __name__ == '__main__':
    result = build()
    (CURATED/'history.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:len(result[k]) for k in ('districts','observations','terms','anchors')}))
