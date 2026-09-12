#!/usr/bin/env python3
"""
Upload scenario logs to CloudWatch Log Groups.

Creates log groups and streams for each scenario's evidence logs.
Timestamps are shifted to recent time (CloudWatch has 14-day ingestion limit).
Also generates a modified incident report with shifted timestamps.

Structure:
  /rca-agent/scenarios/{scenario-name}/{service-name}

Usage:
  # Upload specific scenario (recommended)
  python scripts/upload_logs_to_cloudwatch.py --scenario volte-call-drop-handover

  # Upload all scenarios
  python scripts/upload_logs_to_cloudwatch.py --all

  # Delete all uploaded logs
  python scripts/upload_logs_to_cloudwatch.py --delete-all

Environment:
  AWS_REGION: AWS region (default: us-east-1)
"""

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Log group prefix for all RCA agent scenarios
LOG_GROUP_PREFIX = "/rca-agent/scenarios"

# Scenarios directory
SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def parse_log_line(line: str) -> tuple[datetime | None, str]:
    """Parse a log line to extract timestamp and message."""
    # Match ISO format timestamps: 2024-03-15T14:00:00.123Z
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(.*)$", line
    )
    if match:
        ts_str = match.group(1)
        _message = match.group(2)
        try:
            # Handle with/without milliseconds and Z suffix
            ts_str = ts_str.rstrip("Z")
            if "." in ts_str:
                dt = datetime.fromisoformat(ts_str)
            else:
                dt = datetime.fromisoformat(ts_str)
            return dt, line  # Keep full line as message
        except ValueError:
            pass
    return None, line


def get_scenarios() -> list[str]:
    """Get list of available scenarios."""
    scenarios = []
    for path in SCENARIOS_DIR.iterdir():
        if path.is_dir() and (path / "evidence").exists():
            scenarios.append(path.name)
    return sorted(scenarios)


def upload_scenario_logs(scenario_name: str, client, dry_run: bool = False) -> dict:
    """Upload logs for a single scenario. Returns stats including time offset."""
    scenario_path = SCENARIOS_DIR / scenario_name
    evidence_path = scenario_path / "evidence"

    if not evidence_path.exists():
        print(f"  No evidence directory for {scenario_name}")
        return {"uploaded": 0, "skipped": 0, "offset": None}

    log_group_name = f"{LOG_GROUP_PREFIX}/{scenario_name}"
    stats = {"uploaded": 0, "skipped": 0, "offset": None}

    # Create log group
    if not dry_run:
        try:
            client.create_log_group(logGroupName=log_group_name)
            print(f"  Created log group: {log_group_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
                print(f"  Log group exists: {log_group_name}")
            else:
                raise

    # Process each log file
    for log_file in evidence_path.glob("*.log"):
        service_name = (
            log_file.stem
        )  # e.g., "pricing-service" from "pricing-service.log"
        stream_name = service_name

        print(f"  Processing {log_file.name} -> {stream_name}")

        # Create log stream
        if not dry_run:
            try:
                client.create_log_stream(
                    logGroupName=log_group_name, logStreamName=stream_name
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
                    # Delete and recreate to ensure fresh data
                    client.delete_log_stream(
                        logGroupName=log_group_name, logStreamName=stream_name
                    )
                    client.create_log_stream(
                        logGroupName=log_group_name, logStreamName=stream_name
                    )
                else:
                    raise

        # Parse and upload log events
        events = []
        raw_timestamps = []
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                ts, message = parse_log_line(line)
                if ts:
                    raw_timestamps.append(ts)
                    events.append({"original_ts": ts, "message": message})
                else:
                    # Line without timestamp - skip or use current time
                    stats["skipped"] += 1
                    continue

        if events and not dry_run:
            # Shift timestamps to recent (CloudWatch rejects events > 14 days old)
            # Calculate offset to make the latest event be 1 hour ago
            if raw_timestamps:
                latest_log_ts = max(raw_timestamps)
                now = datetime.now()
                offset = now - latest_log_ts - timedelta(hours=1)
                stats["offset"] = offset  # Store for incident report generation

                for event in events:
                    shifted_ts = event["original_ts"] + offset
                    event["timestamp"] = int(shifted_ts.timestamp() * 1000)
                    del event["original_ts"]

            # Sort by timestamp (required by CloudWatch)
            events.sort(key=lambda x: x["timestamp"])

            # Upload in batches (CloudWatch limit: 10,000 events per batch)
            batch_size = 10000
            for i in range(0, len(events), batch_size):
                batch = events[i : i + batch_size]
                client.put_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream_name,
                    logEvents=batch,
                )

            stats["uploaded"] += len(events)
            print(f"    Uploaded {len(events)} log events")

    return stats


def delete_all_logs(client, dry_run: bool = False):
    """Delete all RCA agent log groups."""
    paginator = client.get_paginator("describe_log_groups")

    for page in paginator.paginate(logGroupNamePrefix=LOG_GROUP_PREFIX):
        for log_group in page["logGroups"]:
            name = log_group["logGroupName"]
            if dry_run:
                print(f"  Would delete: {name}")
            else:
                print(f"  Deleting: {name}")
                client.delete_log_group(logGroupName=name)


def generate_cloudwatch_incident(
    scenario_name: str, offset: timedelta, dry_run: bool = False
) -> Path | None:
    """Generate a modified incident report with shifted timestamps for CloudWatch."""
    scenario_path = SCENARIOS_DIR / scenario_name
    incident_path = scenario_path / "incident.md"
    output_path = scenario_path / "incident_cloudwatch.md"

    if not incident_path.exists():
        print(f"  No incident.md found for {scenario_name}")
        return None

    content = incident_path.read_text()

    # Extract the base date from the incident for time-only replacements
    base_date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", content)
    if base_date_match:
        base_year, base_month, base_day = base_date_match.groups()
        base_date = datetime(int(base_year), int(base_month), int(base_day))
    else:
        base_date = datetime.now()

    # Pattern to match full timestamps: 2024-03-15 14:00:00 or 2024-03-15T14:00:00
    date_pattern = r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})"

    def replace_full_timestamp(match):
        year, month, day, hour, minute, second = match.groups()
        original = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )
        shifted = original + offset
        return shifted.strftime("%Y-%m-%d %H:%M:%S")

    modified_content = re.sub(date_pattern, replace_full_timestamp, content)

    # Pattern for time-only: matches HH:MM:SS or HH:MM (not preceded by date)
    # This handles "- 14:45:00" style patterns
    time_only_pattern = r"(?<!\d[ T])(\d{2}):(\d{2})(?::(\d{2}))?(?=\s|$|[^\d])"

    def replace_time_only(match):
        hour, minute, second = match.groups()
        second = second or "00"
        original = datetime(
            base_date.year,
            base_date.month,
            base_date.day,
            int(hour),
            int(minute),
            int(second),
        )
        shifted = original + offset
        if match.group(3):  # Had seconds
            return shifted.strftime("%H:%M:%S")
        return shifted.strftime("%H:%M")

    modified_content = re.sub(time_only_pattern, replace_time_only, modified_content)

    # Add a header noting this is auto-generated
    header = f"""<!-- AUTO-GENERATED for CloudWatch demo - timestamps shifted to recent time -->
<!-- Original: {incident_path.name} | Generated: {datetime.now(timezone.utc).isoformat()} -->

"""
    modified_content = header + modified_content

    if dry_run:
        print(f"  Would generate: {output_path}")
        return None

    output_path.write_text(modified_content)
    print(f"  Generated: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Upload scenario logs to CloudWatch")
    parser.add_argument("--scenario", help="Upload specific scenario")
    parser.add_argument("--all", action="store_true", help="Upload all scenarios")
    parser.add_argument(
        "--delete-all", action="store_true", help="Delete all uploaded logs"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--list", action="store_true", help="List available scenarios")

    args = parser.parse_args()

    if args.list:
        print("Available scenarios:")
        for s in get_scenarios():
            print(f"  {s}")
        return

    client = boto3.client("logs", region_name=args.region)

    if args.delete_all:
        print("Deleting all RCA agent log groups...")
        delete_all_logs(client, args.dry_run)
        print("Done!")
        return

    if not args.scenario and not args.all:
        parser.print_help()
        sys.exit(1)

    scenarios = [args.scenario] if args.scenario else get_scenarios()

    print(f"Uploading logs to CloudWatch (region: {args.region})")
    print(f"Log group prefix: {LOG_GROUP_PREFIX}")
    print()

    total_stats = {"uploaded": 0, "skipped": 0}
    generated_incidents = []

    for scenario in scenarios:
        print(f"Scenario: {scenario}")
        stats = upload_scenario_logs(scenario, client, args.dry_run)
        total_stats["uploaded"] += stats["uploaded"]
        total_stats["skipped"] += stats["skipped"]

        # Generate modified incident report with shifted timestamps
        if stats.get("offset"):
            incident_path = generate_cloudwatch_incident(
                scenario, stats["offset"], args.dry_run
            )
            if incident_path:
                generated_incidents.append((scenario, incident_path))
        print()

    print(
        f"Total: {total_stats['uploaded']} events uploaded, {total_stats['skipped']} skipped"
    )

    if generated_incidents:
        print()
        print("Generated CloudWatch-compatible incident reports:")
        for scenario, path in generated_incidents:
            print(f"  {path}")

    print()
    print("To run the agent with CloudWatch backend:")
    print()
    print("  export RCA_AGENT_MODE=production")
    print("  export LOG_SEARCH_BACKEND=cloudwatch")
    print(f"  export CLOUDWATCH_LOG_GROUP_PREFIX={LOG_GROUP_PREFIX}")
    print(f"  export AWS_REGION={args.region}")
    print()
    if generated_incidents:
        scenario, incident_path = generated_incidents[0]
        print("  # Use the generated incident report with shifted timestamps:")
        print(f"  python src/run_demo.py {scenario} --incident {incident_path}")
    else:
        print(f"  python src/run_demo.py {scenarios[0]}")


if __name__ == "__main__":
    main()
