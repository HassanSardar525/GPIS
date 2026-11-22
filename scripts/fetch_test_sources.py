"""Acquire the exact public originals used by ingestion and release checks."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import os
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory

import httpx


ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data/curated"


def mirrored_health_pdf(client):
    register = json.loads((CURATED / "health_capacity_periods.json").read_text(encoding="utf8"))
    url = register["sources"]["punjab_health_statistics_2023"]["acquisition_url"]
    with TemporaryDirectory() as directory:
        archive = Path(directory) / "punjab-health-statistics.rar"
        with client.stream("GET", url) as response, archive.open("wb") as file:
            response.raise_for_status()
            for block in response.iter_bytes():
                file.write(block)
        tar = "tar" if os.name == "nt" else "bsdtar"
        return subprocess.check_output([tar, "-xOf", str(archive), "Punjab Health Statistics/PHS2024.pdf"])


def fetch_sources(use_health_mirror=False):
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
                if use_health_mirror and item["source_id"] == "punjab_health_statistics_2024":
                    contents = mirrored_health_pdf(client)
                else:
                    response = client.get(source["url"])
                    response.raise_for_status()
                    contents = response.content
                if sha256(contents).hexdigest() != expected:
                    raise ValueError(f"Downloaded source differs from reviewed checksum: {target.name}")
                target.parent.mkdir(exist_ok=True, parents=True)
                with NamedTemporaryFile(dir=target.parent, delete=False) as temp:
                    temp.write(contents)
                Path(temp.name).replace(target)
            print(f"Verified {target.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--health-mirror", action="store_true", help="Read PHS2024 from the verified multi-edition archive")
    fetch_sources(parser.parse_args().health_mirror)
