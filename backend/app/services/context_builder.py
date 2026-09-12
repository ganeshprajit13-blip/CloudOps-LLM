import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("cloudops.services.context_builder")

class ContextBuilder:
    """
    Combines normalized AWS cloud context and detected signals into a compact,
    structured text representation formatted into clear sections for LLM reasoning.
    """

    def filter_context_by_resource(
        self,
        cloud_context: Dict[str, Any],
        resource_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Filter cloud context to focus on a specific resource ID if provided,
        while preserving essential related network and security context.
        """
        if not resource_id or not cloud_context:
            return cloud_context or {}

        r_id = resource_id.strip().lower()
        import copy
        filtered = copy.deepcopy(cloud_context)

        target_inst = None
        target_inst_id = None
        target_vpc_id = None
        target_subnet_id = None
        target_sg_ids = set()

        resources = filtered.get("resources", {})
        if isinstance(resources, dict) and "ec2" in resources:
            ec2_instances = resources.get("ec2", [])
            matching_ec2 = [
                inst for inst in ec2_instances
                if isinstance(inst, dict) and r_id in str(inst.get("instance_id", "")).lower()
            ]
            if matching_ec2:
                resources["ec2"] = matching_ec2
                target_inst = matching_ec2[0]
                target_inst_id = str(target_inst.get("instance_id", "")).lower()
                target_vpc_id = str(target_inst.get("vpc_id", "")).lower() if target_inst.get("vpc_id") else None
                target_subnet_id = str(target_inst.get("subnet_id", "")).lower() if target_inst.get("subnet_id") else None
                target_sg_ids = {str(sg_id).lower() for sg_id in target_inst.get("security_group_ids", [])}

        # Filter Security Groups
        if isinstance(resources, dict) and "security_groups" in resources:
            sgs = resources.get("security_groups", [])
            if target_inst:
                filtered_sgs = [
                    sg for sg in sgs
                    if isinstance(sg, dict) and str(sg.get("group_id", "")).lower() in target_sg_ids
                ]
            else:
                filtered_sgs = [
                    sg for sg in sgs
                    if isinstance(sg, dict) and (
                        r_id in str(sg.get("group_id", "")).lower() or r_id in str(sg.get("name", "")).lower()
                    )
                ]
            resources["security_groups"] = filtered_sgs

        # Filter Host Telemetry
        if isinstance(resources, dict) and "host_telemetry" in resources:
            hosts = resources.get("host_telemetry", [])
            filtered_hosts = [
                h for h in hosts
                if isinstance(h, dict) and (
                    r_id in str(h.get("instance_id", "")).lower()
                    or (target_inst_id and target_inst_id in str(h.get("instance_id", "")).lower())
                )
            ]
            resources["host_telemetry"] = filtered_hosts

        # Filter VPC Infrastructure
        retained_rt_ids = set()
        if isinstance(resources, dict) and "vpc" in resources and isinstance(resources["vpc"], dict):
            vpc_data = resources["vpc"]
            # Subnets
            if "subnets" in vpc_data:
                subnets = vpc_data.get("subnets", [])
                if target_subnet_id:
                    vpc_data["subnets"] = [
                        s for s in subnets
                        if isinstance(s, dict) and (
                            str(s.get("subnet_id", "")).lower() == target_subnet_id
                            or (target_vpc_id and str(s.get("vpc_id", "")).lower() == target_vpc_id)
                        )
                    ]
                elif target_vpc_id:
                    vpc_data["subnets"] = [
                        s for s in subnets
                        if isinstance(s, dict) and str(s.get("vpc_id", "")).lower() == target_vpc_id
                    ]

            # Route Tables
            if "route_tables" in vpc_data:
                rts = vpc_data.get("route_tables", [])
                if target_inst:
                    filtered_rts = []
                    for rt in rts:
                        if not isinstance(rt, dict):
                            continue
                        rt_vpc = str(rt.get("vpc_id", "")).lower()
                        if target_vpc_id and rt_vpc != target_vpc_id:
                            continue
                        assocs = rt.get("associations", [])
                        is_assoc = False
                        if not assocs:
                            is_assoc = True
                        else:
                            for a in assocs:
                                if isinstance(a, dict):
                                    if target_subnet_id and str(a.get("subnet_id", "")).lower() == target_subnet_id:
                                        is_assoc = True
                                        break
                                    if a.get("main", False) and rt_vpc == target_vpc_id:
                                        is_assoc = True
                                        break
                        if is_assoc:
                            filtered_rts.append(rt)
                            if rt.get("route_table_id"):
                                retained_rt_ids.add(str(rt.get("route_table_id")).lower())
                    vpc_data["route_tables"] = filtered_rts
                else:
                    for rt in rts:
                        if isinstance(rt, dict) and rt.get("route_table_id"):
                            retained_rt_ids.add(str(rt.get("route_table_id")).lower())

        # Filter Load Balancers
        if isinstance(resources, dict) and "load_balancers" in resources:
            albs = resources.get("load_balancers", [])
            if target_inst_id:
                filtered_albs = []
                for alb in albs:
                    if not isinstance(alb, dict):
                        continue
                    has_tg = False
                    for tg in alb.get("target_groups", []):
                        for ut in tg.get("unhealthy_targets", []):
                            if target_inst_id in str(ut.get("target_id", "")).lower():
                                has_tg = True
                                break
                    if has_tg:
                        filtered_albs.append(alb)
                resources["load_balancers"] = filtered_albs

        # Filter Metrics
        if "metrics" in filtered:
            metrics = filtered.get("metrics", [])
            filtered_metrics = [
                m for m in metrics
                if isinstance(m, dict) and (
                    r_id in str(m.get("resource_id", "")).lower()
                    or (target_inst_id and target_inst_id in str(m.get("resource_id", "")).lower())
                )
            ]
            filtered["metrics"] = filtered_metrics

        # Filter Signals
        if "signals" in filtered:
            signals = filtered.get("signals", [])
            relevant_signals = []
            for s in signals:
                if not isinstance(s, dict):
                    continue
                s_res = str(s.get("resource_id", "")).lower()
                s_type = s.get("type", "")
                s_meta = s.get("metadata", {}) or {}

                if r_id in s_res or (target_inst_id and target_inst_id in s_res):
                    relevant_signals.append(s)
                    continue

                if s_type == "port_not_allowed":
                    sg_id = str(s_meta.get("group_id", "")).lower()
                    if sg_id in target_sg_ids or s_res in target_sg_ids:
                        relevant_signals.append(s)
                        continue

                if s_type == "missing_default_route":
                    rt_id = str(s_meta.get("route_table_id", s_res)).lower()
                    rt_vpc = str(s_meta.get("vpc_id", "")).lower()
                    if (retained_rt_ids and rt_id in retained_rt_ids) or (target_vpc_id and rt_vpc == target_vpc_id):
                        relevant_signals.append(s)
                        continue

                if s_type == "unhealthy_load_balancer_target":
                    if target_inst_id and target_inst_id in s_res:
                        relevant_signals.append(s)
                        continue

                if s_type == "recent_infrastructure_change":
                    rel_ids = {r_id}
                    if target_inst_id:
                        rel_ids.add(target_inst_id)
                    rel_ids.update(target_sg_ids)
                    if target_subnet_id:
                        rel_ids.add(target_subnet_id)
                    if target_vpc_id:
                        rel_ids.add(target_vpc_id)
                    if any(rid in s_res for rid in rel_ids if rid):
                        relevant_signals.append(s)
                        continue

            filtered["signals"] = relevant_signals

        # Filter CloudTrail Events
        if "cloudtrail_events" in filtered:
            events = filtered.get("cloudtrail_events", [])
            rel_ids = {r_id}
            if target_inst_id:
                rel_ids.add(target_inst_id)
            rel_ids.update(target_sg_ids)
            if target_subnet_id:
                rel_ids.add(target_subnet_id)
            if target_vpc_id:
                rel_ids.add(target_vpc_id)

            filtered_events = [
                ev for ev in events
                if isinstance(ev, dict) and any(rid in str(ev.get("resource", "")).lower() for rid in rel_ids if rid)
            ]
            filtered["cloudtrail_events"] = filtered_events

        # Re-derive Evidence Statements and Summary from filtered context
        from app.services.evidence import generate_evidence_statements
        from app.services.preprocessing import compute_summary

        filtered["evidence"] = generate_evidence_statements(filtered.get("signals", []), filtered)
        filtered["summary"] = compute_summary(filtered, filtered.get("signals", []))

        return filtered

    def build_context_text(
        self,
        cloud_context: Dict[str, Any],
        resource_id: Optional[str] = None
    ) -> str:
        """
        Convert normalized cloud context into a compact formatted string split into distinct sections:
        - CURRENT CLOUD STATE
        - DETECTED SIGNALS
        - RECENT EVENTS
        - NETWORK CONFIGURATION
        - SECURITY CONFIGURATION
        - LOAD BALANCER INFORMATION
        """
        if not cloud_context:
            return "CURRENT CLOUD STATE:\nNo live cloud context available."

        context_data = self.filter_context_by_resource(cloud_context, resource_id)

        lines = []

        # 1. CURRENT CLOUD STATE
        lines.append("=== CURRENT CLOUD STATE ===")
        summary = context_data.get("summary", {})
        if isinstance(summary, dict) and summary:
            lines.append(
                f"Summary: Total Instances={summary.get('total_instances', 0)}, "
                f"Running={summary.get('running_instances', 0)}, "
                f"High CPU={summary.get('high_cpu_instances', 0)}, "
                f"Unhealthy Targets={summary.get('unhealthy_targets', 0)}"
            )

        resources = context_data.get("resources", {})
        if isinstance(resources, dict):
            ec2_list = resources.get("ec2", [])
            for inst in ec2_list:
                if isinstance(inst, dict):
                    lines.append(
                        f"- EC2 Instance: id={inst.get('instance_id')}, state={inst.get('state')}, "
                        f"type={inst.get('instance_type')}, public_ip={inst.get('public_ip')}, "
                        f"private_ip={inst.get('private_ip')}, subnet={inst.get('subnet_id')}"
                    )

        # 2. DETECTED SIGNALS
        lines.append("\n=== DETECTED SIGNALS ===")
        signals = context_data.get("signals", [])
        if signals:
            seen_descriptions = set()
            count = 0
            for sig in signals:
                if isinstance(sig, dict):
                    desc = sig.get("description", "")
                    if desc in seen_descriptions:
                        continue
                    seen_descriptions.add(desc)
                    lines.append(
                        f"- Signal [{sig.get('severity', 'info').upper()}]: {sig.get('type')} "
                        f"on {sig.get('resource_id')} -> {desc}"
                    )
                    count += 1
                    if count >= 10:
                        break
        else:
            lines.append("No anomaly signals detected.")

        # 3. RECENT EVENTS
        lines.append("\n=== RECENT EVENTS (AUDIT HISTORY) ===")
        ct_events = context_data.get("cloudtrail_events", [])
        if ct_events:
            lines.append("Note: Audit events represent historical activity. The active Security Group and host state below reflects current operational reality.")
            # Filter for significant modification events (or fallback to recent events if none)
            mod_keywords = ["authorize", "revoke", "create", "delete", "modify", "stop", "start", "update", "put", "attach", "detach"]
            filtered_events = [
                ev for ev in ct_events
                if isinstance(ev, dict) and any(kw in str(ev.get("event_name", "")).lower() for kw in mod_keywords)
            ]
            events_to_show = (filtered_events if filtered_events else ct_events)[:5]
            for ev in events_to_show:
                if isinstance(ev, dict):
                    lines.append(
                        f"- Event: name={ev.get('event_name')}, time={ev.get('event_time')}, "
                        f"actor={ev.get('principal')}, resource={ev.get('resource')}"
                    )
        else:
            lines.append("No recent CloudTrail modification events.")

        # 4. NETWORK CONFIGURATION
        lines.append("\n=== NETWORK CONFIGURATION ===")
        if isinstance(resources, dict) and "vpc" in resources:
            vpc_info = resources.get("vpc", {})
            if isinstance(vpc_info, dict):
                subnets = vpc_info.get("subnets", [])
                for sub in subnets:
                    if isinstance(sub, dict):
                        lines.append(f"- Subnet: id={sub.get('subnet_id')}, vpc={sub.get('vpc_id')}, cidr={sub.get('cidr')}")
                
                r_tables = vpc_info.get("route_tables", [])
                for rt in r_tables:
                    if isinstance(rt, dict):
                        routes_summary = ", ".join(
                            f"{r.get('destination')}->{r.get('target')}"
                            for r in rt.get("routes", []) if isinstance(r, dict)
                        )
                        lines.append(f"- Route Table: id={rt.get('route_table_id')}, routes=[{routes_summary}]")

                igws = vpc_info.get("internet_gateways", [])
                if igws:
                    lines.append(f"- Internet Gateways: {igws}")
                nats = vpc_info.get("nat_gateways", [])
                if nats:
                    lines.append(f"- NAT Gateways: {nats}")
        else:
            lines.append("Standard VPC network configuration.")

        # 5. SECURITY CONFIGURATION
        lines.append("\n=== SECURITY CONFIGURATION (CURRENT ACTIVE STATE) ===")
        sg_list = resources.get("security_groups", []) if isinstance(resources, dict) else []
        if sg_list:
            lines.append("Note: The active inbound rules below represent current ground truth.")
            for sg in sg_list:
                if isinstance(sg, dict):
                    rules_str = []
                    for r in sg.get("inbound_rules", []):
                        if isinstance(r, dict):
                            rules_str.append(
                                f"proto={r.get('protocol')}, ports={r.get('from_port')}-{r.get('to_port')}, sources={r.get('sources')}"
                            )
                    lines.append(f"- Security Group: id={sg.get('group_id')}, name={sg.get('name')}, rules=[{'; '.join(rules_str)}]")
        else:
            lines.append("No specific security group detail available in live context.")

        # 6. LOAD BALANCER INFORMATION
        lines.append("\n=== LOAD BALANCER INFORMATION ===")
        alb_list = resources.get("load_balancers", []) if isinstance(resources, dict) else []
        if alb_list:
            for alb in alb_list:
                if isinstance(alb, dict):
                    tg_info = []
                    for tg in alb.get("target_groups", []):
                        if isinstance(tg, dict):
                            unhealthy = [
                                f"target={u.get('target_id')} ({u.get('reason')})"
                                for u in tg.get("unhealthy_targets", []) if isinstance(u, dict)
                            ]
                            tg_info.append(
                                f"TargetGroup={tg.get('name')} port={tg.get('port')} path={tg.get('health_check_path')} unhealthy={unhealthy}"
                            )
                    lines.append(f"- ALB: name={alb.get('name')}, state={alb.get('state')}, target_groups=[{'; '.join(tg_info)}]")
        else:
            lines.append("No ALB load balancer configured for this environment.")

        # 7. HOST-LEVEL & OS SERVICE TELEMETRY
        lines.append("\n=== HOST-LEVEL & OS SERVICE TELEMETRY ===")
        host_list = resources.get("host_telemetry", []) if isinstance(resources, dict) else []
        if host_list:
            for host in host_list:
                if isinstance(host, dict):
                    h_id = host.get("instance_id", "unknown")
                    h_plat = host.get("platform", "windows")
                    svcs_str = []
                    for s in host.get("services", []):
                        if isinstance(s, dict):
                            svcs_str.append(f"{s.get('name')} ({s.get('display_name', s.get('name'))}): Status={s.get('status')} [StartType={s.get('start_type')}]")
                    ports_str = []
                    for p in host.get("listening_ports", []):
                        if isinstance(p, dict):
                            ports_str.append(f"Port {p.get('port')}:{p.get('state')}")
                    sys_info = host.get("system_info", {})
                    sys_str = f", OS={sys_info.get('os_name')}" if sys_info and sys_info.get('os_name') else ""
                    
                    svc_summary = ", ".join(svcs_str) if svcs_str else "No target services reported"
                    ports_summary = ", ".join(ports_str) if ports_str else "No active web listening ports reported"
                    lines.append(f"- Host {h_id} ({h_plat}){sys_str}:\n  * Services: [{svc_summary}]\n  * Listening Ports: [{ports_summary}]")
        else:
            lines.append("Standard host operating system telemetry.")

        # 8. CLOUDWATCH METRICS
        lines.append("\n=== CLOUDWATCH METRICS ===")
        metrics_list = context_data.get("metrics", [])
        if metrics_list:
            for m in metrics_list[:10]:
                if isinstance(m, dict):
                    m_name = m.get("metric_name")
                    m_res = m.get("resource_id")
                    m_val = m.get("value")
                    m_max = m.get("maximum")
                    m_avg = m.get("average")
                    m_unit = m.get("unit") or "%"
                    m_ts = m.get("timestamp") or ""
                    ts_str = f" at {m_ts}" if m_ts else ""
                    lines.append(f"- Metric: {m_name} on {m_res} -> Peak={m_max or m_val}{m_unit}, Avg={m_avg or m_val}{m_unit}{ts_str}")
        else:
            lines.append("No CloudWatch metric datapoints recorded in the current observation window.")

        return "\n".join(lines)

