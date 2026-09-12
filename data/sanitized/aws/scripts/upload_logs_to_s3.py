#!/usr/bin/env python3
"""
Upload scenario logs to S3 for Athena querying.

This script:
1. Reads log files from scenario evidence directories
2. Parses them into structured JSON format
3. Uploads to S3 partitioned by date
4. Generates Athena table DDL

Usage:
    python scripts/upload_logs_to_s3.py --bucket my-bucket --all
    python scripts/upload_logs_to_s3.py --bucket my-bucket --scenario volte-call-drop-handover
    python scripts/upload_logs_to_s3.py --generate-ddl --bucket my-bucket

Environment variables:
    AWS_REGION: AWS region (default: us-east-1)
    S3_BUCKET: S3 bucket name (can also use --bucket)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Pattern for valid SQL identifiers (alphanumeric + underscores, must start with letter/underscore)
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(value: str, name: str) -> str:
    """Validate that a value is a safe SQL identifier."""
    if not _VALID_IDENTIFIER.match(value):
        raise ValueError(
            f"Invalid {name}: {value!r}. Must match [a-zA-Z_][a-zA-Z0-9_]*"
        )
    return value


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def parse_log_line(line: str, source_file: str, scenario: str = "") -> Optional[dict]:
    """Parse a log line into structured format."""
    # Skip comments and empty lines
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Common log format: TIMESTAMP LEVEL SERVICE [CATEGORY] MESSAGE
    # Example: 2024-03-15T14:00:00.123Z ERROR pricing-service [DBPool] Connection pool exhausted
    pattern = r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(\w+)\s+(\S+)\s+\[([^\]]+)\]\s+(.*)$"
    match = re.match(pattern, line)

    if match:
        ts_str, level, service, category, message = match.groups()
        return {
            "timestamp": ts_str,
            "level": level,
            "service": service,
            "category": category,
            "message": f"[{category}] {message}",
            "source_file": source_file,
            "scenario": scenario,
        }

    # Simpler format: TIMESTAMP LEVEL SERVICE MESSAGE
    pattern_simple = (
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(\w+)\s+(\S+)\s+(.*)$"
    )
    match = re.match(pattern_simple, line)

    if match:
        ts_str, level, service, message = match.groups()
        return {
            "timestamp": ts_str,
            "level": level,
            "service": service,
            "category": "general",
            "message": message,
            "source_file": source_file,
            "scenario": scenario,
        }

    return None


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse timestamp string to datetime."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str.rstrip("Z"), fmt.rstrip("Z"))
        except ValueError:
            continue
    return None


def process_scenario(scenario_path: Path) -> list[dict]:
    """Process all log files in a scenario's evidence directory."""
    evidence_dir = scenario_path / "evidence"
    if not evidence_dir.exists():
        print(f"  Warning: No evidence directory in {scenario_path.name}")
        return []

    logs = []
    for log_file in evidence_dir.glob("*.log"):
        print(f"  Processing {log_file.name}...")
        with open(log_file) as f:
            for line in f:
                parsed = parse_log_line(line, log_file.name, scenario_path.name)
                if parsed:
                    logs.append(parsed)

    return logs


def partition_logs_by_date(logs: list[dict]) -> dict[str, list[dict]]:
    """Group logs by date for S3 partitioning."""
    partitions = {}
    for log in logs:
        ts = parse_timestamp(log["timestamp"])
        if ts:
            date_key = ts.strftime("%Y/%m/%d")
            if date_key not in partitions:
                partitions[date_key] = []
            partitions[date_key].append(log)
    return partitions


def upload_to_s3(
    bucket: str,
    prefix: str,
    logs: list[dict],
    partition_key: str,
    dry_run: bool = False,
):
    """Upload logs to S3 in JSONL format."""
    import boto3

    s3 = boto3.client("s3")
    key = f"{prefix}/{partition_key}/logs.jsonl"

    # Convert to JSONL
    content = "\n".join(json.dumps(log) for log in logs)

    if dry_run:
        print(f"  Would upload {len(logs)} logs to s3://{bucket}/{key}")
        return

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="application/jsonl",
    )
    print(f"  Uploaded {len(logs)} logs to s3://{bucket}/{key}")


def generate_athena_ddl(
    bucket: str, prefix: str, database: str = "rca_logs", table: str = "logs"
) -> str:
    """Generate Athena table DDL for the uploaded logs."""
    _validate_identifier(database, "database name")
    _validate_identifier(table, "table name")
    ddl = f"""-- Athena Table DDL for RCA Agent Logs
-- Run this in Athena Query Editor to create the table

CREATE DATABASE IF NOT EXISTS {database};

CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{table} (
    `timestamp` string,
    `level` string,
    `service` string,
    `category` string,
    `message` string,
    `source_file` string,
    `scenario` string
)
PARTITIONED BY (
    `year` string,
    `month` string,
    `day` string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    'serialization.format' = '1',
    'ignore.malformed.json' = 'true'
)
LOCATION 's3://{bucket}/{prefix}/'
TBLPROPERTIES (
    'has_encrypted_data' = 'false',
    'projection.enabled' = 'true',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2020,2030',
    'projection.month.type' = 'integer',
    'projection.month.range' = '1,12',
    'projection.month.digits' = '2',
    'projection.day.type' = 'integer',
    'projection.day.range' = '1,31',
    'projection.day.digits' = '2',
    'storage.location.template' = 's3://{bucket}/{prefix}/${{year}}/${{month}}/${{day}}'
);

-- After creating the table, you can query it like this:
-- SELECT * FROM {database}.{table}
-- WHERE timestamp >= '2024-03-15T09:00:00'
--   AND timestamp <= '2024-03-15T15:00:00'
--   AND service = 'pricing-service';
"""  # nosec B608 - DDL generation (not query execution). database/table validated
    # via _validate_identifier() regex ^[a-zA-Z_][a-zA-Z0-9_]*$.
    # bucket/prefix are S3 paths in LOCATION string literals.
    # Output is printed for human review, not executed programmatically.
    return ddl


def main():
    parser = argparse.ArgumentParser(
        description="Upload scenario logs to S3 for Athena"
    )
    parser.add_argument(
        "--bucket", "-b", help="S3 bucket name", default=os.environ.get("S3_BUCKET")
    )
    parser.add_argument("--prefix", "-p", help="S3 key prefix", default="rca-logs")
    parser.add_argument("--scenario", "-s", help="Scenario name to upload")
    parser.add_argument("--all", "-a", action="store_true", help="Upload all scenarios")
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be uploaded"
    )
    parser.add_argument(
        "--generate-ddl", action="store_true", help="Generate Athena table DDL"
    )
    parser.add_argument("--database", default="rca_logs", help="Athena database name")
    parser.add_argument("--table", default="logs", help="Athena table name")
    args = parser.parse_args()

    # Generate DDL only
    if args.generate_ddl:
        if not args.bucket:
            print("Error: --bucket required for DDL generation")
            sys.exit(1)
        ddl = generate_athena_ddl(args.bucket, args.prefix, args.database, args.table)
        print(ddl)
        return

    # Validate args
    if not args.bucket:
        print("Error: --bucket required (or set S3_BUCKET environment variable)")
        sys.exit(1)

    if not args.scenario and not args.all:
        print("Error: Specify --scenario or --all")
        sys.exit(1)

    # Find scenarios directory
    scenarios_dir = Path(__file__).parent.parent / "scenarios"
    if not scenarios_dir.exists():
        print(f"Error: Scenarios directory not found: {scenarios_dir}")
        sys.exit(1)

    # Determine which scenarios to process
    if args.all:
        scenario_paths = [d for d in scenarios_dir.iterdir() if d.is_dir()]
    else:
        scenario_path = scenarios_dir / args.scenario
        if not scenario_path.exists():
            print(f"Error: Scenario not found: {args.scenario}")
            print(
                f"Available: {[d.name for d in scenarios_dir.iterdir() if d.is_dir()]}"
            )
            sys.exit(1)
        scenario_paths = [scenario_path]

    print(f"Processing {len(scenario_paths)} scenarios...")
    print(f"Target: s3://{args.bucket}/{args.prefix}/")
    print()

    all_logs = []
    for scenario_path in scenario_paths:
        print(f"Processing scenario: {scenario_path.name}")
        logs = process_scenario(scenario_path)
        all_logs.extend(logs)
        print(f"  Found {len(logs)} log entries")

    print()
    print(f"Total: {len(all_logs)} log entries")

    # Partition by date
    partitions = partition_logs_by_date(all_logs)
    print(f"Partitions: {list(partitions.keys())}")

    # Upload each partition
    print()
    if args.dry_run:
        print("DRY RUN - would upload:")
    else:
        print("Uploading to S3...")

    for partition_key, logs in partitions.items():
        upload_to_s3(args.bucket, args.prefix, logs, partition_key, args.dry_run)

    print()
    print("Done!")
    print()
    print("Next steps:")
    print(f"  1. Run: python {__file__} --generate-ddl --bucket {args.bucket}")
    print("  2. Execute the DDL in Athena Query Editor")
    print("  3. Set environment variables:")
    print("     export RCA_AGENT_MODE=athena")
    print(f"     export ATHENA_DATABASE={args.database}")
    print(f"     export ATHENA_TABLE={args.table}")
    print(f"     export ATHENA_OUTPUT_LOCATION=s3://{args.bucket}/athena-results/")


if __name__ == "__main__":
    main()
