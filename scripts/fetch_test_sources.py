"""Acquire the exact public originals used by ingestion and release checks."""

from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx


ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data/curated"


def fetch_sources():
    sources = json.loads((CURATED / "punjab_districts.json").read_text(encoding="utf8"))["sources"]
    documents = json.loads((CURATED / "document_sources.json").read_text(encoding="utf8"))
    table_one = json.loads((CURATED / "pbs_table_1.json").read_text(encoding="utf8"))
    legacy = json.loads((CURATED / "districts.json").read_text(encoding="utf8"))["sources"]
    registered = [{**legacy["pbs_table_1"], **table_one}, *documents.values()]
    with httpx.Client(timeout=60, follow_redirects=True, transport=httpx.HTTPTransport(retries=2)) as client:
        for item in registered:
            target = ROOT / item["local_file"]
            expected = item["sha256"]
            if target.exists():
                if sha256(target.read_bytes()).hexdigest() != expected:
                    raise ValueError(f"Existing source differs from reviewed checksum: {target.name}")
            else:
                source = sources[item["source_id"]]
                response = client.get(source["url"])
                response.raise_for_status()
                if sha256(response.content).hexdigest() != expected:
                    raise ValueError(f"Downloaded source differs from reviewed checksum: {target.name}")
                target.parent.mkdir(exist_ok=True, parents=True)
                with NamedTemporaryFile(dir=target.parent, delete=False) as temp:
                    temp.write(response.content)
                Path(temp.name).replace(target)
            print(f"Verified {target.name}")


if __name__ == "__main__":
    fetch_sources()
