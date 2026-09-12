from typing import Any, Dict, List
from app.core.logging import logger


def normalize_ec2_data(raw_instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes EC2 instance telemetry by keeping key troubleshooting fields."""
    normalized = []
    for inst in raw_instances:
        normalized.append({
            "instance_id": inst.get("instance_id"),
            "state": inst.get("state", "unknown"),
            "instance_type": inst.get("instance_type"),
            "private_ip": inst.get("private_ip"),
            "public_ip": inst.get("public_ip"),
            "availability_zone": inst.get("availability_zone"),
            "subnet_id": inst.get("subnet_id"),
            "vpc_id": inst.get("vpc_id"),
            "security_group_ids": inst.get("security_group_ids", []),
            "tags": inst.get("tags", {}),
        })
    return normalized


def normalize_cloudwatch_data(raw_metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes CloudWatch metric statistics into standard compact metric points."""
    normalized = []
    for m in raw_metrics:
        val = m.get("value") if m.get("value") is not None else m.get("average")
        if val is None:
            val = m.get("maximum")

        normalized.append({
            "metric_name": m.get("metric_name"),
            "resource_id": m.get("resource_id"),
            "timestamp": m.get("timestamp"),
            "value": round(float(val), 2) if val is not None else None,
            "average": round(float(m.get("average")), 2) if m.get("average") is not None else None,
            "maximum": round(float(m.get("maximum")), 2) if m.get("maximum") is not None else None,
            "unit": m.get("unit"),
        })
    return normalized


def normalize_cloudtrail_data(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes CloudTrail management events."""
    normalized = []
    for e in raw_events:
        res_name = None
        if e.get("resources"):
            res_name = e["resources"][0].get("resource_name")

        normalized.append({
            "event_time": e.get("event_time"),
            "event_name": e.get("event_name"),
            "event_source": e.get("event_source"),
            "principal": e.get("username"),
            "region": e.get("aws_region"),
            "resource": res_name,
        })
    return normalized


def normalize_vpc_data(raw_vpc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes VPC, Subnet, Route Table, IGW, and NAT Gateway resources."""
    vpcs = [
        {
            "vpc_id": v.get("vpc_id"),
            "cidr": v.get("cidr_block"),
            "state": v.get("state"),
        }
        for v in raw_vpc.get("vpcs", [])
    ]

    subnets = [
        {
            "subnet_id": s.get("subnet_id"),
            "vpc_id": s.get("vpc_id"),
            "cidr": s.get("cidr_block"),
            "availability_zone": s.get("availability_zone"),
        }
        for s in raw_vpc.get("subnets", [])
    ]

    route_tables = []
    for rt in raw_vpc.get("route_tables", []):
        routes = [
            {
                "destination": r.get("destination_cidr_block"),
                "target": r.get("gateway_id") or r.get("nat_gateway_id") or r.get("instance_id"),
                "state": r.get("state"),
            }
            for r in rt.get("routes", [])
        ]
        route_tables.append({
            "route_table_id": rt.get("route_table_id"),
            "vpc_id": rt.get("vpc_id"),
            "routes": routes,
            "associations": rt.get("associations", []),
        })

    igws = [igw.get("internet_gateway_id") for igw in raw_vpc.get("internet_gateways", []) if igw.get("internet_gateway_id")]
    nats = [nat.get("nat_gateway_id") for nat in raw_vpc.get("nat_gateways", []) if nat.get("nat_gateway_id")]

    return {
        "vpcs": vpcs,
        "subnets": subnets,
        "route_tables": route_tables,
        "internet_gateways": igws,
        "nat_gateways": nats,
    }


def normalize_security_group_data(raw_sgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes Security Groups and inbound rules."""
    normalized = []
    for sg in raw_sgs:
        inbound = [
            {
                "protocol": rule.get("protocol"),
                "from_port": rule.get("from_port"),
                "to_port": rule.get("to_port"),
                "sources": rule.get("sources", []),
            }
            for rule in sg.get("inbound_rules", [])
        ]

        normalized.append({
            "group_id": sg.get("group_id"),
            "name": sg.get("name"),
            "vpc_id": sg.get("vpc_id"),
            "inbound_rules": inbound,
        })
    return normalized


def normalize_load_balancer_data(raw_lbs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes Application Load Balancers, Target Groups, and Target Health."""
    normalized = []
    for lb in raw_lbs:
        tgs = []
        for tg in lb.get("target_groups", []):
            unhealthy_targets = []
            for th in tg.get("target_health", []):
                if th.get("health_state") and th.get("health_state").lower() != "healthy":
                    unhealthy_targets.append({
                        "target_id": th.get("target_id"),
                        "reason": th.get("reason"),
                        "description": th.get("description"),
                    })

            tgs.append({
                "name": tg.get("target_group_name"),
                "port": tg.get("port"),
                "protocol": tg.get("protocol"),
                "health_check_path": tg.get("health_check_path"),
                "unhealthy_targets": unhealthy_targets,
            })

        normalized.append({
            "name": lb.get("name"),
            "type": lb.get("type"),
            "state": lb.get("state"),
            "dns_name": lb.get("dns_name"),
            "vpc_id": lb.get("vpc_id"),
            "target_groups": tgs,
        })
    return normalized


def normalize_host_telemetry(raw_host_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes host-level OS and service telemetry."""
    normalized = []
    for host in raw_host_data:
        services = []
        win32_services = []
        process_status = []
        for svc in host.get("services", []):
            name = svc.get("name", "")
            status = svc.get("status", "Unknown")
            start_type = svc.get("start_type", "Unknown")
            display_name = svc.get("display_name", name)
            services.append({
                "name": name,
                "display_name": display_name,
                "status": status,
                "start_type": start_type,
            })
            win32_services.append({
                "name": name,
                "display_name": display_name,
                "status": status,
                "start_type": start_type,
            })
            process_status.append({
                "process_name": name,
                "status": status,
            })

        ports = []
        for p in host.get("listening_ports", []):
            ports.append({
                "port": p.get("port"),
                "local_address": p.get("local_address"),
                "state": p.get("state", "Listen"),
                "owning_process": p.get("owning_process"),
            })

        normalized.append({
            "instance_id": host.get("instance_id"),
            "platform": host.get("platform", "windows"),
            "collection_method": host.get("collection_method", "ssm_run_command"),
            "services": services,
            "listening_ports": ports,
            "win32_service": win32_services,
            "process_status": process_status,
            "system_info": host.get("system_info", {}),
            "error": host.get("error"),
        })
    return normalized


def normalize_aws_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Central normalizer combining telemetry across all AWS services."""
    logger.info("Starting AWS raw telemetry normalization")

    region = raw_data.get("region", "unknown")
    timestamp = raw_data.get("timestamp", "")

    ec2_norm = normalize_ec2_data(raw_data.get("ec2", []))
    host_norm = normalize_host_telemetry(raw_data.get("host_telemetry", []))
    cw_norm = normalize_cloudwatch_data(raw_data.get("cloudwatch", []))
    ct_norm = normalize_cloudtrail_data(raw_data.get("cloudtrail", []))
    vpc_norm = normalize_vpc_data(raw_data.get("vpc", {}))
    sg_norm = normalize_security_group_data(raw_data.get("security_groups", []))
    alb_norm = normalize_load_balancer_data(raw_data.get("load_balancers", []))

    logger.info("AWS telemetry normalization completed")

    return {
        "region": region,
        "timestamp": timestamp,
        "resources": {
            "ec2": ec2_norm,
            "host_telemetry": host_norm,
            "vpc": vpc_norm,
            "security_groups": sg_norm,
            "load_balancers": alb_norm,
        },
        "metrics": cw_norm,
        "cloudtrail_events": ct_norm,
    }


normalize_cloud_context = normalize_aws_data


