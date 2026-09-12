from datetime import datetime, timezone
from typing import Any, Dict, List
from app.core.logging import logger
from app.services.evidence import generate_evidence_statements
from app.services.normalizer import normalize_aws_data


def extract_signals(normalized_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts deterministic, observable signals from normalized telemetry."""
    signals: List[Dict[str, Any]] = []
    resources = normalized_data.get("resources", {})

    # 1. CloudWatch Metric Signals (Grouped per instance)
    cpu_metrics_by_instance: Dict[str, List[Dict[str, Any]]] = {}
    metrics = normalized_data.get("metrics", [])
    for m in metrics:
        if m.get("metric_name") == "CPUUtilization" and m.get("value") is not None:
            res_id = m.get("resource_id", "unknown")
            cpu_metrics_by_instance.setdefault(res_id, []).append(m)

    for res_id, inst_metrics in cpu_metrics_by_instance.items():
        peak_val = max(
            (m.get("maximum") if m.get("maximum") is not None else m.get("value", 0.0))
            for m in inst_metrics
        )
        avg_val = round(sum(m.get("value", 0.0) for m in inst_metrics) / len(inst_metrics), 2)
        if peak_val >= 80.0:
            signals.append({
                "type": "high_cpu",
                "severity": "high",
                "resource_id": res_id,
                "description": f"High CPU utilization of {peak_val}% observed on instance {res_id}.",
                "value": peak_val,
                "metadata": {
                    "metric_name": "CPUUtilization",
                    "max_value": peak_val,
                    "avg_value": avg_val,
                    "datapoints_count": len(inst_metrics),
                },
            })
        else:
            signals.append({
                "type": "normal_cpu",
                "severity": "info",
                "resource_id": res_id,
                "description": f"Normal CPU utilization of {peak_val}% observed on instance {res_id}.",
                "value": peak_val,
                "metadata": {
                    "metric_name": "CPUUtilization",
                    "max_value": peak_val,
                    "avg_value": avg_val,
                    "datapoints_count": len(inst_metrics),
                },
            })

    # Map EC2 instance IDs to attached Security Group IDs
    ec2_sg_map = {}
    ec2_instances = resources.get("ec2", [])
    for inst in ec2_instances:
        if isinstance(inst, dict):
            inst_id = inst.get("instance_id")
            for sg_id in inst.get("security_group_ids", []):
                ec2_sg_map.setdefault(sg_id, []).append(inst_id)

    # Helper to distinguish state changes from read-only/lookup events
    def is_mutation_event(event_name: str) -> bool:
        if not event_name or not isinstance(event_name, str):
            return False
        name_lower = event_name.strip().lower()
        read_prefixes = ("describe", "get", "list", "lookup", "head", "view")
        if any(name_lower.startswith(prefix) for prefix in read_prefixes):
            return False
        if name_lower in ("updateinstanceinformation",):
            return False
        mutation_keywords = [
            "authorize", "revoke", "create", "delete", "modify", "stop",
            "start", "update", "put", "attach", "detach", "reboot",
            "terminate", "associate", "disassociate", "replace"
        ]
        return any(kw in name_lower for kw in mutation_keywords)

    # 2. Security Group Signals (e.g. Inbound TCP 443 / 80 missing check)
    security_groups = resources.get("security_groups", [])
    for sg in security_groups:
        sg_id = sg.get("group_id", "unknown")
        sg_name = sg.get("name", "")
        inbound_rules = sg.get("inbound_rules", [])
        attached_instances = ec2_sg_map.get(sg_id, [])
        primary_inst_id = attached_instances[0] if attached_instances else sg_id

        # Check for port 443 and port 80
        has_443 = False
        has_80 = False
        for rule in inbound_rules:
            proto = str(rule.get("protocol", "")).lower()
            from_p = rule.get("from_port")
            to_p = rule.get("to_port")

            if proto in ["tcp", "-1"]:
                if from_p is None or (from_p <= 443 <= (to_p if to_p is not None else from_p)):
                    has_443 = True
                if from_p is None or (from_p <= 80 <= (to_p if to_p is not None else from_p)):
                    has_80 = True

        name_suffix = f" ({sg_name})" if sg_name else ""

        if not has_80:
            signals.append({
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": primary_inst_id,
                "description": f"Security Group {sg_id}{name_suffix} does not allow inbound TCP 80 (HTTP) traffic.",
                "value": 80,
                "metadata": {
                    "group_id": sg_id,
                    "group_name": sg_name,
                    "port": 80,
                    "protocol": "tcp",
                    "instance_id": attached_instances[0] if attached_instances else None,
                    "attached_instances": attached_instances,
                },
            })

        if not has_443:
            signals.append({
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": primary_inst_id,
                "description": f"Security Group {sg_id}{name_suffix} does not allow inbound TCP 443 (HTTPS) traffic.",
                "value": 443,
                "metadata": {
                    "group_id": sg_id,
                    "group_name": sg_name,
                    "port": 443,
                    "protocol": "tcp",
                    "instance_id": attached_instances[0] if attached_instances else None,
                    "attached_instances": attached_instances,
                },
            })


    # 3. ALB Target Health Signals
    albs = resources.get("load_balancers", [])
    for alb in albs:
        for tg in alb.get("target_groups", []):
            tg_name = tg.get("name", "unknown")
            for ut in tg.get("unhealthy_targets", []):
                target_id = ut.get("target_id", "unknown")
                reason = ut.get("reason", "UnknownReason")
                signals.append({
                    "type": "unhealthy_load_balancer_target",
                    "severity": "high",
                    "resource_id": target_id,
                    "description": f"Load Balancer target {target_id} in target group {tg_name} is unhealthy.",
                    "value": "unhealthy",
                    "metadata": {
                        "target_group": tg_name,
                        "reason": reason,
                        "description": ut.get("description"),
                    },
                })

    # 4. CloudTrail Change Signals (Only mutating actions)
    ct_events = normalized_data.get("cloudtrail_events", [])
    for event in ct_events:
        event_name = event.get("event_name", "")
        if not is_mutation_event(event_name):
            continue

        principal = event.get("principal", "unknown")
        res_name = event.get("resource") or "resource"
        event_time = event.get("event_time")

        signals.append({
            "type": "recent_infrastructure_change",
            "severity": "medium",
            "resource_id": res_name,
            "description": f"Recent CloudTrail event {event_name} performed by {principal} on {res_name}.",
            "value": event_name,
            "metadata": {
                "principal": principal,
                "event_time": event_time,
                "event_source": event.get("event_source"),
                "event_name": event_name,
            },
        })

    # 5. Route Table Signals
    vpc_res = resources.get("vpc", {})
    route_tables = vpc_res.get("route_tables", [])
    for rt in route_tables:
        rt_id = rt.get("route_table_id", "unknown")
        routes = rt.get("routes", [])

        has_default = False
        for r in routes:
            dest = r.get("destination")
            target = r.get("target")
            if dest == "0.0.0.0/0" and target:
                has_default = True
                break

        if not has_default and len(routes) > 0:
            signals.append({
                "type": "missing_default_route",
                "severity": "high",
                "resource_id": rt_id,
                "description": f"Route Table {rt_id} has no default route (0.0.0.0/0) to an Internet Gateway or NAT Gateway.",
                "value": "missing_default_route",
                "metadata": {
                    "route_table_id": rt_id,
                    "vpc_id": rt.get("vpc_id"),
                    "associations": rt.get("associations", []),
                },
            })

    # 6. Host-Level / Windows Service Signals
    host_telemetry_list = resources.get("host_telemetry", [])
    for host in host_telemetry_list:
        inst_id = host.get("instance_id", "unknown")
        services = host.get("services", [])
        for svc in services:
            svc_name = svc.get("name", "")
            svc_status = str(svc.get("status", "")).lower()
            display_name = svc.get("display_name") or svc_name
            start_type = svc.get("start_type", "")

            # Emit a windows_service_stopped signal for ANY stopped/paused service.
            # This includes IIS (W3SVC, WAS, IISADMIN), Spooler, and others, so that
            # the heuristic routing in inference.py can intercept them before the LLM
            # attempts to guess the root cause without proper context.
            if svc_status in ["stopped", "stop_pending", "paused"]:
                signals.append({
                    "type": "windows_service_stopped",
                    "severity": "high",
                    "resource_id": inst_id,
                    "description": f"Windows service '{svc_name}' ({display_name}) is Stopped on instance {inst_id}.",
                    "value": "Stopped",
                    "metadata": {
                        "service_name": svc_name,
                        "display_name": display_name,
                        "status": svc.get("status"),
                        "start_type": start_type,
                        "instance_id": inst_id,
                    },
                })

        # Check listening ports if host port telemetry is present
        ports = host.get("listening_ports", [])
        if ports:
            active_ports = {p.get("port") for p in ports if p.get("port") is not None}
            if 80 not in active_ports:
                signals.append({
                    "type": "port_not_listening",
                    "severity": "medium",
                    "resource_id": inst_id,
                    "description": f"Port 80 (HTTP) is not in a listening state on host {inst_id}.",
                    "value": 80,
                    "metadata": {
                        "port": 80,
                        "instance_id": inst_id,
                        "active_listening_ports": sorted(list(active_ports)),
                    },
                })

    return signals


def compute_summary(normalized_data: Dict[str, Any], signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes high-level counts and signal tallies for context summary."""
    ec2_instances = normalized_data.get("resources", {}).get("ec2", [])
    total_instances = len(ec2_instances)
    running_instances = sum(1 for i in ec2_instances if i.get("state") == "running")

    high_cpu_count = sum(1 for s in signals if s.get("type") == "high_cpu")
    unhealthy_targets_count = sum(1 for s in signals if s.get("type") == "unhealthy_load_balancer_target")
    recent_changes_count = sum(1 for s in signals if s.get("type") == "recent_infrastructure_change")
    stopped_services_count = sum(1 for s in signals if s.get("type") == "windows_service_stopped")

    blocked_ports = []
    for s in signals:
        if s.get("type") == "port_not_allowed":
            port_val = s.get("value") or (s.get("metadata") or {}).get("port") or 80
            blocked_ports.append({
                "port": port_val,
                "security_group_id": s.get("resource_id"),
            })

    return {
        "total_instances": total_instances,
        "running_instances": running_instances,
        "high_cpu_instances": high_cpu_count,
        "unhealthy_targets": unhealthy_targets_count,
        "recent_changes": recent_changes_count,
        "stopped_services": stopped_services_count,
        "blocked_ports": blocked_ports,
    }



def preprocess_cloud_context(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point for Phase 3 preprocessing. Converts raw AWS data to CloudOps context."""
    logger.info("Starting CloudOps context preprocessing")

    # Step 1: Normalize raw telemetry
    normalized = normalize_aws_data(raw_data)

    # Step 2: Extract observable signals
    signals = extract_signals(normalized)

    # Step 3: Compute summary metrics
    summary = compute_summary(normalized, signals)

    # Step 4: Generate factual evidence statements
    evidence = generate_evidence_statements(signals, normalized)

    logger.info(f"Preprocessing complete: {len(signals)} signals extracted, {len(evidence)} evidence statements generated")

    return {
        "timestamp": normalized.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "region": normalized.get("region", "unknown"),
        "summary": summary,
        "resources": normalized.get("resources", {}),
        "metrics": normalized.get("metrics", []),
        "cloudtrail_events": normalized.get("cloudtrail_events", []),
        "signals": signals,
        "evidence": evidence,
    }
