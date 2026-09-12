#!/usr/bin/env python3
"""
Ingest scenario logs into an OpenSearch Serverless collection.

Usage:
    python scripts/ingest_to_opensearch_serverless.py \
        --endpoint https://xxx.us-west-2.aoss.amazonaws.com \
        --region us-west-2

Indexes all scenario log files from scenarios/*/evidence/*.log into
an 'rca-logs' index with proper mappings.
"""

import argparse
import re
from pathlib import Path

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
INDEX_NAME = "rca-logs"

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)")
_LEVEL_RE = re.compile(r"\b(ERROR|WARN|INFO|DEBUG)\b")


# All scenarios with evidence/ directories
def get_scenarios() -> list[str]:
    """Get list of scenarios with evidence directories."""
    scenarios = []
    for path in SCENARIOS_DIR.iterdir():
        if path.is_dir() and (path / "evidence").exists():
            scenarios.append(path.name)
    return sorted(scenarios)


def get_client(endpoint: str, region: str) -> OpenSearch:
    """Create OpenSearch client with IAM SigV4 auth for Serverless."""
    credentials = boto3.Session().get_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        "aoss",
        session_token=credentials.token,
    )
    # Serverless needs explicit host/port dict format
    host = endpoint.replace("https://", "").rstrip("/")
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )


def create_index(client: OpenSearch):
    """Create the rca-logs index with proper mappings."""
    mapping = {
        "settings": {"number_of_shards": 2, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "service": {"type": "keyword"},
                "level": {"type": "keyword"},
                "message": {"type": "text"},
                "scenario": {"type": "keyword"},
            }
        },
    }

    try:
        client.indices.create(index=INDEX_NAME, body=mapping)
        print(f"Created index '{INDEX_NAME}'")
    except Exception as e:
        if "resource_already_exists_exception" in str(e).lower():
            print(f"Index '{INDEX_NAME}' already exists, continuing...")
        else:
            raise


def parse_log_line(line: str, service: str, scenario: str) -> dict | None:
    """Parse a single log line into a document."""
    line = line.strip()
    if not line:
        return None
    m = _TS_RE.match(line)
    if not m:
        return None
    timestamp = m.group(1)
    level_m = _LEVEL_RE.search(line)
    level = level_m.group(1) if level_m else "INFO"
    return {
        "timestamp": timestamp,
        "service": service,
        "level": level,
        "message": line,
        "scenario": scenario,
    }


def ingest_scenario(client: OpenSearch, scenario_name: str) -> int:
    """Bulk-index all log files from a scenario. Returns doc count."""
    evidence_dir = SCENARIOS_DIR / scenario_name / "evidence"
    if not evidence_dir.exists():
        print(f"  Skipping {scenario_name}: no evidence/ directory")
        return 0

    actions = []
    for log_file in sorted(evidence_dir.glob("*.log")):
        service = log_file.stem
        for line in log_file.read_text().splitlines():
            doc = parse_log_line(line, service, scenario_name)
            if doc:
                actions.append(
                    {
                        "_index": INDEX_NAME,
                        "_source": doc,
                    }
                )

    if not actions:
        print(f"  Skipping {scenario_name}: no parseable log lines")
        return 0

    # Bulk index in batches
    success, errors = helpers.bulk(
        client, actions, chunk_size=500, raise_on_error=False
    )
    if errors:
        print(f"  {scenario_name}: {success} indexed, {len(errors)} errors")
        for err in errors[:3]:
            print(f"    Error: {err}")
    else:
        print(f"  {scenario_name}: {success} documents indexed")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Ingest scenario logs into OpenSearch Serverless"
    )
    parser.add_argument(
        "--endpoint", required=True, help="OpenSearch Serverless endpoint URL"
    )
    parser.add_argument(
        "--region", default="us-west-2", help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=None,
        help="Specific scenarios to ingest (default: all with evidence/)",
    )
    args = parser.parse_args()

    print(f"Connecting to {args.endpoint} (region: {args.region})...")
    client = get_client(args.endpoint, args.region)

    # Serverless doesn't support info() — verify by listing indices
    try:
        indices = client.cat.indices(format="json")
        print(
            f"Connected. Existing indices: {[i['index'] for i in indices] if indices else 'none'}"
        )
    except Exception:
        # cat.indices may also not be supported — just proceed
        print("Connected (skipping index listing on Serverless)")

    create_index(client)

    scenarios = args.scenarios if args.scenarios else get_scenarios()

    total = 0
    for scenario in scenarios:
        n = ingest_scenario(client, scenario)
        total += n

    # Refresh to make docs searchable
    try:
        client.indices.refresh(index=INDEX_NAME)
    except Exception:
        print("Note: explicit refresh not supported (expected for Serverless)")

    print(f"\nTotal: {total} documents indexed into '{INDEX_NAME}'")


if __name__ == "__main__":
    main()
