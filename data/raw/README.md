# Raw source acquisition

Raw documents are intentionally ignored by Git. Download them into this directory using the filenames below before running source-inspection utilities.

| Local filename | Official source |
|---|---|
| `pbs_census_2023_table_1_punjab.xlsx` | <https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_punjab_districts.xlsx> |
| `pbs_census_2023_table_12_punjab.xlsx` | <https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_12_punjab_districts.xlsx> |
| `agp_punjab_south_dha_2024-25.pdf` | <https://www.agp.gov.pk/SiteImage/Policy/AR%20on%20the%20accounts%20of%2017%20%20district%20hrealt%20authorities%20of%20punjab%20south%202024-25.pdf> |
| `punjab_health_statistics_2023.pdf` | <https://bos.punjab.gov.pk/system/files/PHS2023.pdf> |
| `punjab_health_statistics_2024.pdf` | <https://bos.punjab.gov.pk/sites/bos.punjab.gov.pk/files/PHS2024.pdf> |

The application itself runs from `data/curated/districts.json` and does not require these files.

Before accepting new data, record its publisher, title, period, official URL, table/page locator, and retrieval date. Never overwrite an old-period source with a new-period file under the same name.

The reviewed hashes, acquisition details, comparability decisions, and Table 3 locators for the two health editions are stored in `data/curated/health_capacity_periods.json`. Raw PDFs and mirror archives remain ignored by Git.


- `agp_punjab_north_dha_2023-24.pdf`: [Official AGP North Punjab DHA report](https://agp.gov.pk/SiteImage/Policy/03-Comp.%20Audit-DHA%20AY%20%282023-24%29-Approved%20by%20AGP.pdf), downloaded 2026-09-06. Audit year 2023–24, budget tables for financial year 2022–23. SHA-256 and exact district pages are recorded in `data/curated/punjab_services.json`.
