"""Reproduce the explicitly reviewed provincial register; no inferred dates."""
import json
from pathlib import Path

sources = {
 'punjab_cm_history': dict(title='Our Chief Ministers', publisher='Office of the Chief Minister, Punjab', period='Historical offices; reviewed 27 October 2026', url='https://cm.punjab.gov.pk/index.php/chief-ministers', locator='Named chief-minister history entries', reviewed_excerpt='Official history lists Shahbaz Sharif, Hasan Askari Rizvi, Usman Buzdar, Hamza Shahbaz, Parvez Elahi, Mohsin Naqvi and Maryam Nawaz. Records retain oath-date and handover qualifications.'),
 'elahi_oath': dict(title='President administers oath to Parvez Elahi', publisher='Press Information Department, Government of Pakistan', period='27 July 2022', url='https://pid.gov.pk/site/press_detail/20388', locator='PR No. 151; oath ceremony paragraph', reviewed_excerpt='The Presidency records the chief minister oath on 27 July 2022. The CM history lists 26 July; this register uses the oath event and retains the discrepancy.'),
 'naqvi_oath': dict(title='Mohsin Naqvi takes oath as caretaker Punjab CM', publisher='Pakistan Broadcasting Corporation', period='Event 22 January 2023; published 23 January', url='https://www.radio.gov.pk/23-01-2023/mohsin-naqvi-takes-oath-as-punjab-caretaker-cm', locator='Opening paragraphs: Sunday-night oath', reviewed_excerpt='The Monday 23 January article reports the oath occurred Sunday night, 22 January. This matches the official CM history. Publication date is not used as the oath date.'),
 'caretaker_portfolios': dict(title='Caretaker Punjab portfolios assigned', publisher='Pakistan Broadcasting Corporation', period='27 January 2023', url='https://radio.gov.pk/27-01-2023/mohsin-naqvi-assigns-portfolios-to-caretaker-punjab-ministers', locator='Portfolio allocation paragraph', reviewed_excerpt='Javaid Akram is named for Specialized Healthcare, Jamal Nasir for Primary and Secondary Healthcare, and Mansoor Qadir for Higher and School Education. Ministers took oath the preceding day. Exact portfolio notification and end dates still need review.')
}
rows = [
 ('shahbaz-2013','Muhammad Shahbaz Sharif','PML-N','2013-06-07','2018-06-07',False),
 ('askari-2018','Hasan Askari Rizvi',None,'2018-06-07','2018-08-20',True),
 ('buzdar-2018','Usman Buzdar','PTI','2018-08-20','2022-04-30',False),
 ('hamza-2022','Hamza Shahbaz','PML-N','2022-04-30','2022-07-25',False),
 ('elahi-2022','Parvez Elahi','PML-Q','2022-07-27','2023-01-22',False),
 ('naqvi-2023','Mohsin Naqvi',None,'2023-01-22','2024-02-25',True),
 ('maryam-2024','Maryam Nawaz Sharif','PML-N','2024-02-26',None,False),
]
terms=[]
for identity,name,party,start,end,caretaker in rows:
    t=dict(id=identity,person=name,role='Chief minister',responsibility='provincial_executive',portfolio='Punjab government',party=party,caretaker=caretaker,vacancy=False,start=start,end=end,start_precision='day',end_precision='day' if end else 'open',verified_through='2026-10-27' if not end else None,status='verified',notes=['Dates from official CM history. Shared handover dates may include both officeholders; spending is never divided by days.'],districts=[],constituency=None,boundary_edition=None,mapping_anchor_ids=[],source_ids=['punjab_cm_history'])
    if identity in ('shahbaz-2013','askari-2018'):
        t.update(start_precision='awaiting_review',status='awaiting_review')
        t['notes'].append('History start may be a selection/appointment date. Oath notification needed; excluded from exact tenure calculations.')
    if identity=='hamza-2022':
        t.update(end_precision='awaiting_review',status='awaiting_review')
        t['notes'].append('History ends 25 July; Presidency records succession court direction on 26 July and oath on 27 July. Exact handover needs review.')
    if identity=='elahi-2022':
        t['source_ids'].append('elahi_oath')
        t['notes'].append('27 July oath used instead of 26 July in summary history. PML-Q affiliation is during this term.')
    if identity=='naqvi-2023':
        t['source_ids'].append('naqvi_oath')
        t['notes'].append('Sunday-night oath was 22 January, not the 23 January publication date. Caretaker is a role status, not a party.')
    terms.append(t)
for identity,name,portfolio in [('javaid-akram-2023','Javaid Akram','Specialized Healthcare'),('jamal-nasir-2023','Jamal Nasir','Primary and Secondary Healthcare'),('mansoor-qadir-2023','Mansoor Qadir','Higher Education and School Education')]:
    terms.append(dict(id=identity,person=name,role='Provincial minister',responsibility='provincial_executive',portfolio=portfolio,party=None,caretaker=True,vacancy=False,start=None,end=None,start_precision='unknown',end_precision='unknown',verified_through=None,status='awaiting_review',notes=['Portfolio reported 27 January 2023; cabinet oath reported as 26 January. Portfolio start/end notifications not reviewed; no precise tenure inferred.'],districts=[],constituency=None,boundary_edition=None,mapping_anchor_ids=[],source_ids=['caretaker_portfolios']))
register=[
 dict(domain='education',url='https://www.pbs.gov.pk/censusarchive/',from_year=2017,status='awaiting_review',reason='2017 district literacy tables identified. Definitions, denominator and boundary crosswalk require review before comparison to 2023.'),
 dict(domain='health',url='https://bos.punjab.gov.pk/dataset',from_year=2017,status='awaiting_review',reason='Four institution-count categories compared across January/December 2023 for all 36 districts after original-page review. Earlier editions and health outcomes remain unverified.'),
 dict(domain='spending',url='https://agp.gov.pk/',from_year=2017,status='awaiting_review',reason='South comparative development table reviewed for all 17 listed authorities. North figures retained; cross-year geography/definitions await review. Spending is nominal, DHA-only.'),
 dict(domain='officeholders',url='https://www.pap.gov.pk/members/listing/en/22',from_year=2017,status='awaiting_review',reason='2021 biographies support a dated representation snapshot. Assembly/ECP oath, vacancy, by-election and boundary notifications are needed for full terms.')]

if __name__=='__main__':
    path=Path(__file__).resolve().parents[1]/'data/curated/officeholder_register.json'
    path.write_text(json.dumps(dict(sources=sources,terms=terms,source_register=register),indent=2,ensure_ascii=False)+'\n',encoding='utf8',newline='\n')
