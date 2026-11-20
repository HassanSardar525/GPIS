"""Prepare explicitly configured test databases before order-independent tests."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture(scope='session', autouse=True)
def prepare_configured_databases():
    from app.database.seed import seed_database
    root=Path(__file__).resolve().parents[1]
    for variable in ('GPIS_TEST_DATABASE_URL','GPIS_PUNJAB_TEST_DATABASE_URL'):
        url=os.getenv(variable)
        if not url:
            continue
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,
            env={**os.environ,'GPIS_DATABASE_URL':url},check=True)
        if variable=='GPIS_TEST_DATABASE_URL':
            seed_database(url,root/'data/curated/districts.json','prototype-v1')
