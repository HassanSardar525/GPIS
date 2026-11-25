"""Manual transcription of visually reviewed scanned PHS 2023 Table 3 rows.

Counts only, column order: hospitals, dispensaries, RHCs, BHUs.
Row centres refer to original full-page previews at 918 x 1188 pixels.
All five pages and their matching PHS 2024 pages were visually reviewed.
"""
import json
from pathlib import Path

ROWS = [
 (19,'bahawalnagar',342,[6,29,10,104]),(19,'bahawalpur',456,[12,70,13,77]),
 (19,'rahim-yar-khan',591,[6,65,22,107]),(19,'dera-ghazi-khan',707,[7,23,10,55]),
 (19,'layyah',803,[8,34,6,36]),(19,'muzaffargarh',880,[6,45,14,76]),(19,'rajanpur',977,[5,13,7,32]),
 (20,'chiniot',321,[3,12,3,38]),(20,'faisalabad',398,[21,116,21,173]),
 (20,'jhang',533,[8,75,10,61]),(20,'toba-tek-singh',628,[8,29,8,74]),
 (20,'gujranwala',744,[11,59,14,99]),(20,'gujrat',839,[15,6,10,93]),
 (20,'hafizabad',916,[2,16,8,33]),(20,'mandi-bahauddin',974,[5,8,11,49]),
 (21,'narowal',286,[3,8,7,57]),(21,'sialkot',368,[10,27,9,90]),
 (21,'kasur',492,[8,32,13,83]),(21,'lahore',596,[50,118,25,7]),
 (21,'nankana-sahib',720,[4,23,9,49]),(21,'sheikhupura',803,[11,25,9,84]),(21,'khanewal',948,[7,11,10,81]),
 (22,'lodhran',290,[5,17,5,48]),(22,'multan',366,[22,47,8,84]),(22,'vehari',463,[4,37,14,75]),
 (22,'attock',558,[7,9,6,62]),(22,'chakwal',693,[6,18,16,63]),
 (22,'jhelum',809,[7,26,7,48]),(22,'rawalpindi',904,[15,22,8,107]),
 (23,'okara',325,[8,29,10,97]),(23,'pakpattan',414,[6,10,5,55]),
 (23,'sahiwal',480,[9,26,11,78]),(23,'bhakkar',568,[5,30,6,40]),
 (23,'khushab',679,[6,38,6,45]),(23,'mianwali',789,[6,20,10,42]),(23,'sargodha',877,[17,12,13,131]),
]

if __name__=='__main__':
    result = dict(source_id='punjab_health_statistics_2023',sha256='8c7c99b08bd0adfafc3afd324e1551797cbfc6ecd78dd920f7cf177db03aa6e8',snapshot_date='2023-01-01',reviewed_on='2026-10-27',
        review='Original scanned pages 19–23 / printed pages 4–8 and corresponding PHS 2024 pages visually checked. Same four institution columns, district and component tehsil lists, and contributing agencies. Administrative splits remain within the original district rows in both editions. Changes can reflect reporting revisions; this is capacity, not health outcomes.',
        rows=[dict(district=slug,pdf_page=page,printed_page=str(page-15),counts=dict(zip(['hospitals','dispensaries','rhcs','bhus'],counts)),rectangle=[124/918,(y-10)/1188,794/918,(y+10)/1188]) for page,slug,y,counts in ROWS])
    path=Path(__file__).resolve().parents[1]/'data/curated/health_history_review.json'
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n')
