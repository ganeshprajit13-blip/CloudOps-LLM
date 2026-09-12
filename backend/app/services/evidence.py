from typing import Any, Dict, List
from app.core.logging import logger


def generate_evidence_statements(signals: List[Dict[str, Any]], normalized_context: Dict[str, Any]) -> List[str]:
    """Generates factual, human-readable evidence statements strictly derived from observed signals."""
    logger.info(f"Generating evidence statements from {len(signals)} observed signals")
    evidence: List[str] = []

    for sig in signals:
        sig_type = sig.get("type")
        res_id = sig.get("resource_id", "unknown")
        desc = sig.get("description", "")
        meta = sig.get("metadata", {})
        val = sig.get("value")

        if sig_type == "high_cpu":
            evidence.append(f"EC2 instance {res_id} has high CPU utilization of {val}%.")
        elif sig_type == "port_not_allowed":
            port = meta.get("port", val)
            sg_id = meta.get("group_id", res_id)
            inst_id = meta.get("instance_id")
            sg_name = meta.get("group_name", "")
            name_str = f" ({sg_name})" if sg_name else ""
            proto = str(meta.get("protocol", "TCP")).upper()

            if inst_id and inst_id != sg_id:
                evidence.append(f"EC2 instance {inst_id} is attached to Security Group {sg_id}{name_str}.")
            evidence.append(f"Security Group {sg_id}{name_str} does not contain an inbound {proto} {port} rule.")
            evidence.append(f"Inbound {proto} port {port} is not permitted by Security Group {sg_id}{name_str}.")
        elif sig_type == "unhealthy_load_balancer_target":
            tg_name = meta.get("target_group", "unknown")
            reason = meta.get("reason")
            reason_str = f" (Reason: {reason})" if reason else ""
            evidence.append(f"ALB target {res_id} in target group {tg_name} is reported as unhealthy{reason_str}.")
        elif sig_type == "recent_infrastructure_change":
            event_name = val or meta.get("event_name", "event")
            principal = meta.get("principal", "principal")
            event_time = meta.get("event_time", "")
            time_str = f" at {event_time}" if event_time else ""
            evidence.append(f"CloudTrail recorded {event_name} on {res_id} by principal {principal}{time_str}.")
        elif sig_type == "missing_default_route":
            evidence.append(f"Route Table {res_id} is missing an active default route (0.0.0.0/0) to an Internet Gateway or NAT Gateway.")
        elif sig_type == "windows_service_stopped":
            svc_name = meta.get("service_name", "Service")
            disp_name = meta.get("display_name") or svc_name
            status_val = meta.get("status", "Stopped")
            start_type = meta.get("start_type", "")
            start_str = f" (configured StartType: {start_type})" if start_type else ""
            evidence.append(f"Host telemetry confirms Windows service '{svc_name}' ({disp_name}) status is {status_val} on EC2 instance {res_id}{start_str}.")
            if "w3svc" in svc_name.lower():
                evidence.append(f"World Wide Web Publishing Service (W3SVC / IIS) is not running on EC2 instance {res_id}.")
        elif sig_type == "port_not_listening":
            port = meta.get("port", val)
            evidence.append(f"Host port telemetry confirms port {port} is not in a listening state on EC2 instance {res_id}.")
        else:
            if desc:
                evidence.append(desc)


    logger.info(f"Generated {len(evidence)} evidence statements")
    return evidence
