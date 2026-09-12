import json
import re
import logging
from typing import Dict, Any, Tuple, List, Optional
from app.schemas.analysis import DiagnosisSchema

logger = logging.getLogger("cloudops.services.diagnosis_validator")

REQUIRED_SCHEMA_KEYS = [
    "problem",
    "probable_root_cause",
    "evidence",
    "impact",
    "recommendation",
    "confidence",
]

FORBIDDEN_AUTONOMOUS_TERMS = [
    "i fixed",
    "i have restarted",
    "i deleted",
    "i modified",
    "i created",
    "automatically modify",
    "automatically deleted",
    "automatically restarted",
    "restarting the ec2 instance now",
    "executing remediation",
]

FIELD_ALIASES = {
    "problem": [
        "problem", "problem_description", "issue", "issue_description",
        "summary", "description", "incident_summary", "title"
    ],
    "probable_root_cause": [
        "probable_root_cause", "root_cause", "probable_cause", "cause",
        "underlying_cause", "root_cause_analysis", "reason"
    ],
    "evidence": [
        "evidence", "evidence_list", "facts", "supporting_evidence",
        "observations", "signals"
    ],
    "impact": [
        "impact", "operational_impact", "impact_statement", "consequence",
        "affected_services"
    ],
    "recommendation": [
        "recommendation", "recommendations", "remediation", "suggested_action",
        "resolution_steps", "remediation_steps", "corrective_action", "remedy"
    ],
    "confidence": [
        "confidence", "confidence_score", "certainty", "score"
    ]
}


def safe_extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse the primary JSON object from raw model generation text.
    Handles codeblocks (```json ... ```), embedded JSON, trailing commas, or surrounding prose.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    cleaned = raw_text.strip()

    # Strategy 1: Match ```json {...} ``` or ``` {...} ``` codeblock pattern
    codeblock_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.IGNORECASE)
    if codeblock_match:
        try:
            parsed = json.loads(codeblock_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # Strategy 2: First balanced JSON object starting from first '{'
    first_brace = cleaned.find("{")
    if first_brace != -1:
        substring = cleaned[first_brace:]

        # 2a. Fast standard JSONDecoder.raw_decode
        try:
            decoder = json.JSONDecoder()
            parsed, _ = decoder.raw_decode(substring)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 2b. Balanced brace scanner to capture first complete JSON
        brace_depth = 0
        in_string = False
        escape = False
        for i, char in enumerate(substring):
            if char == '"' and not escape:
                in_string = not in_string
            elif char == '\\' and in_string:
                escape = not escape
                continue
            elif not in_string:
                if char == '{':
                    brace_depth += 1
                elif char == '}':
                    brace_depth -= 1
                    if brace_depth == 0:
                        first_json_str = substring[: i + 1]
                        try:
                            parsed = json.loads(first_json_str)
                            if isinstance(parsed, dict):
                                return parsed
                        except Exception:
                            cleaned_cand = re.sub(r",\s*([\}\]])", r"\1", first_json_str)
                            try:
                                parsed = json.loads(cleaned_cand)
                                if isinstance(parsed, dict):
                                    return parsed
                            except Exception:
                                pass
                        break
            escape = False

    # Strategy 3: Outermost braces substring fallback
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        outer = cleaned[first_brace : last_brace + 1].strip()
        try:
            parsed = json.loads(outer)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            cleaned_cand = re.sub(r",\s*([\}\]])", r"\1", outer)
            try:
                parsed = json.loads(cleaned_cand)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    return None


def normalize_diagnosis_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes a diagnosis payload into the canonical schema required by DiagnosisSchema:
    - problem: str
    - probable_root_cause: str
    - evidence: list of str
    - impact: str
    - recommendation: str
    - confidence: float in [0.0, 1.0]

    Maps alias field names (e.g. root_cause -> probable_root_cause, issue -> problem)
    and coerces types if necessary.
    """
    if not isinstance(data, dict):
        return {}

    normalized = dict(data)

    # 1. Alias mapping
    for canonical_key, aliases in FIELD_ALIASES.items():
        if canonical_key not in normalized or normalized[canonical_key] is None or (isinstance(normalized[canonical_key], str) and not normalized[canonical_key].strip()):
            for alias in aliases:
                if alias in normalized and normalized[alias] is not None:
                    val = normalized[alias]
                    if isinstance(val, str) and not val.strip():
                        continue
                    normalized[canonical_key] = val
                    break

    # 2. Type coercion & defaults for required fields
    prob = normalized.get("problem")
    if isinstance(prob, list):
        normalized["problem"] = "; ".join(str(x) for x in prob)
    elif not isinstance(prob, str) or not prob.strip():
        normalized["problem"] = "Reported cloud infrastructure anomaly."
    else:
        normalized["problem"] = prob.strip()

    rc = normalized.get("probable_root_cause")
    if isinstance(rc, list):
        normalized["probable_root_cause"] = "; ".join(str(x) for x in rc)
    elif not isinstance(rc, str) or not rc.strip():
        normalized["probable_root_cause"] = "Insufficient evidence available to conclusively identify root cause."
    else:
        normalized["probable_root_cause"] = rc.strip()

    ev = normalized.get("evidence")
    if isinstance(ev, str):
        normalized["evidence"] = [ev.strip()] if ev.strip() else []
    elif isinstance(ev, list):
        normalized["evidence"] = [str(x).strip() for x in ev if str(x).strip()]
    else:
        normalized["evidence"] = []

    imp = normalized.get("impact")
    if isinstance(imp, list):
        normalized["impact"] = "; ".join(str(x) for x in imp)
    elif not isinstance(imp, str) or not imp.strip():
        normalized["impact"] = "Infrastructure connectivity or service availability may be impacted."
    else:
        normalized["impact"] = imp.strip()

    rec = normalized.get("recommendation")
    if isinstance(rec, list):
        normalized["recommendation"] = "; ".join(str(x) for x in rec)
    elif not isinstance(rec, str) or not rec.strip():
        normalized["recommendation"] = "Review security group rules, network routing, and host telemetry."
    else:
        normalized["recommendation"] = rec.strip()

    conf = normalized.get("confidence")
    if isinstance(conf, bool) or conf is None:
        normalized["confidence"] = 0.50
    else:
        try:
            val = float(conf)
            normalized["confidence"] = max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            normalized["confidence"] = 0.50

    return normalized


class DiagnosisValidator:
    """
    Validates diagnosis schema, confidence range, advisory safety, and evidence grounding.
    """

    def safe_extract_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        return safe_extract_json(raw_text)

    def normalize_diagnosis_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_diagnosis_payload(data)

    def validate_schema(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate that data contains all required diagnosis keys with correct types and ranges.
        """
        if not isinstance(data, dict):
            return False, "Diagnosis payload is not a JSON object."

        for key in REQUIRED_SCHEMA_KEYS:
            if key not in data:
                return False, f"Missing required field: '{key}'"

        if not isinstance(data["problem"], str) or not data["problem"].strip():
            return False, "Field 'problem' must be a non-empty string."

        if not isinstance(data["probable_root_cause"], str) or not data["probable_root_cause"].strip():
            return False, "Field 'probable_root_cause' must be a non-empty string."

        if not isinstance(data["evidence"], list):
            return False, "Field 'evidence' must be a list."

        if not isinstance(data["impact"], str) or not data["impact"].strip():
            return False, "Field 'impact' must be a non-empty string."

        if not isinstance(data["recommendation"], str) or not data["recommendation"].strip():
            return False, "Field 'recommendation' must be a non-empty string."

        conf = data["confidence"]
        if not isinstance(conf, (int, float)) or isinstance(conf, bool):
            return False, "Field 'confidence' must be a numeric float or integer."

        conf_float = float(conf)
        if conf_float < 0.0 or conf_float > 1.0:
            return False, f"Field 'confidence' value ({conf_float}) must be between 0.0 and 1.0."

        return True, None

    def enforce_advisory_safety(
        self,
        data: Dict[str, Any],
        cloud_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ensure recommendations remain strictly advisory.
        Sanitize any autonomous action claims.
        Additionally, correct 'Start the EC2 instance' recommendations when the EC2 is
        actually running and the root cause is a stopped Windows service — the LLM
        has a training bias toward this phrasing even when the instance is healthy.
        """
        cleaned = dict(data)
        # 1. Sanitize autonomous action claims
        rec = cleaned.get("recommendation", "")
        if isinstance(rec, str):
            rec_lower = rec.lower()
            for forbidden in FORBIDDEN_AUTONOMOUS_TERMS:
                if forbidden in rec_lower:
                    cleaned["recommendation"] = (
                        f"Review the identified issue and consider taking corrective action: {rec}"
                    )
                    logger.warning(f"Sanitized autonomous language in recommendation: '{rec}'")
                    break

        ctx = cloud_context or {}
        resources = ctx.get("resources", {}) if isinstance(ctx, dict) else {}
        signals = ctx.get("signals", []) if isinstance(ctx, dict) else []
        cjk_pattern = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")

        # Find EC2 running status and stopped Windows services
        ec2_instances = resources.get("ec2", []) if isinstance(resources, dict) else []
        ec2_running = any(
            isinstance(i, dict) and str(i.get("state", "")).lower() == "running"
            for i in ec2_instances
        )

        stopped_svc_name = None
        stopped_svc_display = None
        for s in signals:
            if isinstance(s, dict) and s.get("type") == "windows_service_stopped":
                meta = s.get("metadata") or {}
                stopped_svc_name = meta.get("service_name") or s.get("resource_id", "")
                stopped_svc_display = meta.get("display_name") or stopped_svc_name
                break
        if not stopped_svc_name:
            for h in (resources.get("host_telemetry", []) if isinstance(resources, dict) else []):
                if isinstance(h, dict):
                    for svc in h.get("services", []):
                        if isinstance(svc, dict) and str(svc.get("status", "")).lower() in ("stopped", "stop_pending", "paused"):
                            stopped_svc_name = svc.get("name", "")
                            stopped_svc_display = svc.get("display_name") or stopped_svc_name
                            break
                if stopped_svc_name:
                    break

        # 2. Recommendation hardening & multilingual sanitization
        rec = cleaned.get("recommendation", "")
        has_cjk_rec = isinstance(rec, str) and bool(cjk_pattern.search(rec))
        mentions_start_ec2 = isinstance(rec, str) and bool(re.search(r'\bstart\b.{0,30}?\bec2\s+instance\b', rec.lower()))

        if ec2_running and stopped_svc_name:
            svc_norm = stopped_svc_name.lower()
            disp_norm = (stopped_svc_display or "").lower()
            if svc_norm == "spooler" or "spooler" in disp_norm or "print spooler" in disp_norm:
                cleaned["recommendation"] = "Start the Print Spooler (Spooler) service on the EC2 instance."
            elif mentions_start_ec2 or has_cjk_rec or not rec or len(rec.strip()) < 10:
                target_inst = ec2_instances[0].get("instance_id", "the EC2 instance") if ec2_instances else "the EC2 instance"
                cleaned["recommendation"] = (
                    f"Start the '{stopped_svc_display or stopped_svc_name}' ({stopped_svc_name}) service on "
                    f"{target_inst} using AWS Systems Manager Run Command or Windows Service Manager."
                )
        elif has_cjk_rec:
            cleaned["recommendation"] = "Investigate host services, Security Group configuration, and application logs to resolve the issue."

        # 3. Impact hardening & multilingual sanitization
        imp = cleaned.get("impact", "")
        has_cjk_imp = isinstance(imp, str) and bool(cjk_pattern.search(imp))
        if has_cjk_imp or not imp or len(imp.strip()) < 5:
            if stopped_svc_name:
                svc_norm = stopped_svc_name.lower()
                if svc_norm == "spooler" or "spooler" in (stopped_svc_display or "").lower():
                    cleaned["impact"] = "Print Spooler service operations and dependent print job processing are unavailable."
                elif svc_norm in ("w3svc", "was", "iisadmin"):
                    cleaned["impact"] = "Hosted web applications and HTTP/HTTPS service endpoints on IIS are unavailable."
                else:
                    cleaned["impact"] = f"The '{stopped_svc_display or stopped_svc_name}' service is stopped, impacting dependent application features."
            else:
                cleaned["impact"] = "Infrastructure connectivity or service availability may be impacted."

        # 4. Problem & Probable Root Cause CJK sanitization
        for field in ("problem", "probable_root_cause"):
            val = cleaned.get(field, "")
            if isinstance(val, str) and cjk_pattern.search(val):
                cleaned_val = cjk_pattern.sub("", val).strip()
                if not cleaned_val:
                    if field == "problem":
                        cleaned_val = "Reported infrastructure anomaly."
                    else:
                        cleaned_val = "Target Windows service is stopped."
                cleaned[field] = cleaned_val

        return cleaned

    def validate_and_filter_evidence(
        self,
        evidence_list: List[str],
        cloud_context: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """
        Validates each evidence statement against the actual ground-truth telemetry
        in cloud_context. Rejects contradictory claims (e.g. claiming port 443 is missing
        when the SG actually allows port 443, or claiming a service is stopped when it is running),
        unrelated resources, or generic read-only CloudTrail events.
        Returns (valid_evidence_list, list_of_rejection_reasons).
        """
        if not evidence_list or not isinstance(evidence_list, list):
            return [], ["Evidence list was empty or not a list."]

        if not cloud_context or not isinstance(cloud_context, dict):
            return [str(e).strip() for e in evidence_list if str(e).strip()], []

        resources = cloud_context.get("resources", {})
        if not isinstance(resources, dict):
            resources = {}
        signals = cloud_context.get("signals", [])
        if not isinstance(signals, list):
            signals = []

        # 1. Extract allowed & blocked ports
        allowed_ports = set()
        sgs = resources.get("security_groups", [])
        if not sgs and "security_groups" in cloud_context:
            sgs = cloud_context.get("security_groups", [])
        if not isinstance(sgs, list):
            sgs = []

        for sg in sgs:
            if not isinstance(sg, dict):
                continue
            for rule in sg.get("inbound_rules", []):
                if not isinstance(rule, dict):
                    continue
                proto = str(rule.get("protocol", "")).lower()
                from_p = rule.get("from_port")
                to_p = rule.get("to_port")
                if proto in ("tcp", "-1"):
                    if from_p is None:
                        allowed_ports.update([80, 443, 22, 3389, 8080, 3306, 5432])
                    elif to_p is not None:
                        for p in range(from_p, min(to_p + 1, from_p + 1000)):
                            allowed_ports.add(p)
                    else:
                        allowed_ports.add(from_p)

        blocked_ports = set()
        for s in signals:
            if isinstance(s, dict) and s.get("type") == "port_not_allowed":
                val = s.get("value")
                if isinstance(val, int):
                    blocked_ports.add(val)
                p_meta = (s.get("metadata") or {}).get("port")
                if isinstance(p_meta, int):
                    blocked_ports.add(p_meta)

        # 2. Extract service statuses
        running_services = set()
        stopped_services = set()
        service_display_names = {}
        hosts = resources.get("host_telemetry", [])
        if not hosts and "host_telemetry" in cloud_context:
            hosts = cloud_context.get("host_telemetry", [])
        if not isinstance(hosts, list):
            hosts = []

        for h in hosts:
            if not isinstance(h, dict):
                continue
            for svc in h.get("services", []):
                if isinstance(svc, dict):
                    raw_name = str(svc.get("name", ""))
                    name = raw_name.lower()
                    status = str(svc.get("status", "")).lower()
                    service_display_names[name] = raw_name
                    if status == "running":
                        running_services.add(name)
                    elif status in ("stopped", "stop_pending", "paused"):
                        stopped_services.add(name)

        # 3. Extract listening ports
        active_listening_ports = set()
        has_host_telemetry = len(hosts) > 0
        for h in hosts:
            if not isinstance(h, dict):
                continue
            for p in h.get("listening_ports", []):
                if isinstance(p, dict) and p.get("port") is not None:
                    try:
                        active_listening_ports.add(int(p.get("port")))
                    except (ValueError, TypeError):
                        pass

        # 4. Extract valid resource IDs
        valid_instance_ids = {
            str(inst.get("instance_id", "")).lower()
            for inst in resources.get("ec2", []) if isinstance(inst, dict) and inst.get("instance_id")
        }
        valid_sg_ids = {
            str(sg.get("group_id", "")).lower()
            for sg in sgs if isinstance(sg, dict) and sg.get("group_id")
        }
        valid_rtb_ids = {
            str(rtb.get("route_table_id", "")).lower()
            for rtb in resources.get("route_tables", []) if isinstance(rtb, dict) and rtb.get("route_table_id")
        }
        valid_vpc_ids = {
            str(vpc.get("vpc_id", "")).lower()
            for vpc in resources.get("vpcs", []) if isinstance(vpc, dict) and vpc.get("vpc_id")
        }
        valid_subnet_ids = {
            str(sub.get("subnet_id", "")).lower()
            for sub in resources.get("subnets", []) if isinstance(sub, dict) and sub.get("subnet_id")
        }

        valid_evidence: List[str] = []
        rejection_reasons: List[str] = []

        missing_port_patterns = [
            r"no\s+evidence\s+of\s+(?:https|http)?\s*\(?port\s*(\d+)\)?",
            r"no\s+(?:inbound\s+)?(?:tcp|udp)?\s*(?:port\s*)?(\d+)\s+rule",
            r"lacks\s+(?:inbound\s+)?(?:tcp|udp)?\s*(?:port\s*)?(\d+)",
            r"missing\s+(?:inbound\s+)?(?:tcp|udp)?\s*(?:port\s*)?(\d+)",
            r"does\s+not\s+allow\s+inbound\s+(?:tcp|udp)?\s*(?:port\s*)?(\d+)",
            r"port\s+(\d+)\s+(?:is\s+)?not\s+permitted",
            r"port\s+(\d+)\s+(?:is\s+)?blocked",
            r"port\s+(\d+)\s+was\s+(?:removed|revoked|deleted)",
            r"(?:removed|revoked|deleted)\s+(?:inbound\s+)?(?:tcp|udp)?\s*(?:port\s*)?(\d+)",
            r"inbound\s+(?:tcp|udp)?\s*port\s*(\d+)\s+was\s+(?:removed|revoked|deleted)",
            r"rule\s+for\s+(?:tcp\s+)?port\s*(\d+)\s+was\s+(?:removed|revoked|deleted)",
        ]

        allowed_port_patterns = [
            r"allows\s+inbound\s+(?:tcp|udp)?\s*(?:port\s*)?(\d+)",
            r"port\s+(\d+)\s+is\s+allowed",
            r"port\s+(\d+)\s+is\s+open",
            r"permits\s+inbound\s+(?:tcp|udp)?\s*(?:port\s*)?(\d+)",
        ]

        for stmt in evidence_list:
            if not isinstance(stmt, str) or not stmt.strip():
                continue
            stmt_clean = stmt.strip()
            stmt_lower = stmt_clean.lower()
            rejected = False

            # Contradiction Check 1: Claiming port is missing/removed/blocked when it is actually allowed
            for pat in missing_port_patterns:
                m = re.search(pat, stmt_lower)
                if m:
                    port_num = int(m.group(1))
                    if port_num in allowed_ports and port_num not in blocked_ports:
                        rejection_reasons.append(
                            f"Contradiction: Evidence claims port {port_num} is missing/removed/blocked, but active Security Group allows port {port_num}."
                        )
                        rejected = True
                        break
            if rejected:
                continue

            # Contradiction Check 2: Claiming port is allowed when it is blocked
            for pat in allowed_port_patterns:
                m = re.search(pat, stmt_lower)
                if m:
                    port_num = int(m.group(1))
                    if port_num in blocked_ports and port_num not in allowed_ports:
                        rejection_reasons.append(
                            f"Contradiction: Evidence claims port {port_num} is allowed, but Security Group blocks port {port_num}."
                        )
                        rejected = True
                        break
            if rejected:
                continue

            # Contradiction Check 3: Claiming a running service is stopped
            if any(svc in stmt_lower for svc in running_services):
                if re.search(r"\b(is\s+stopped|service\s+stopped|crashed|inactive|stopped|was\s+stopped)\b", stmt_lower):
                    for svc in running_services:
                        if svc in stmt_lower and svc not in stopped_services:
                            disp = service_display_names.get(svc, svc)
                            rejection_reasons.append(
                                f"Contradiction: Evidence claims service '{disp}' ({svc}) is stopped, but host telemetry confirms it is Running."
                            )
                            rejected = True
                            break
            if rejected:
                continue

            # Contradiction Check 4: Claiming a stopped service is running
            if any(svc in stmt_lower for svc in stopped_services):
                if re.search(r"\b(is\s+running|service\s+running|active)\b", stmt_lower) and not re.search(r"\b(not\s+running|state\s+is\s+running)\b", stmt_lower):
                    for svc in stopped_services:
                        if svc in stmt_lower and svc not in running_services:
                            disp = service_display_names.get(svc, svc)
                            rejection_reasons.append(
                                f"Contradiction: Evidence claims service '{disp}' ({svc}) is running, but host telemetry confirms it is Stopped."
                            )
                            rejected = True
                            break
            if rejected:
                continue

            # Contradiction Check 5: Listening port state contradiction
            if has_host_telemetry:
                # Claiming port is listening when not in active_listening_ports
                m_listen = re.search(r"port\s+(\d+)\s+is\s+(?:actively\s+)?listening", stmt_lower)
                if m_listen:
                    p_num = int(m_listen.group(1))
                    if p_num not in active_listening_ports:
                        rejection_reasons.append(
                            f"Contradiction: Evidence claims port {p_num} is listening, but host telemetry shows it is not active."
                        )
                        rejected = True
                        continue

                # Claiming port is NOT listening when it IS in active_listening_ports
                m_not_listen = re.search(r"port\s+(\d+)\s+is\s+not\s+listening", stmt_lower)
                if m_not_listen:
                    p_num = int(m_not_listen.group(1))
                    if p_num in active_listening_ports:
                        rejection_reasons.append(
                            f"Contradiction: Evidence claims port {p_num} is not listening, but host telemetry shows it is listening."
                        )
                        rejected = True
                        continue

            # Contradiction Check 6: Generic read-only CloudTrail calls as RCA evidence
            if re.search(r"\b(describe|get|list|lookup)[a-zA-Z0-9_]*\b", stmt_lower) and re.search(r"\b(cloudtrail|api\s+call|event|called|executed)\b", stmt_lower):
                if not re.search(r"\b(failed|error|unauthorized|denied|exception)\b", stmt_lower):
                    rejection_reasons.append(
                        f"Ungrounded/Non-causal: Generic read-only CloudTrail API calls in evidence '{stmt_clean}' do not constitute root cause evidence."
                    )
                    continue

            # Contradiction Check 7: Unrelated resource IDs
            mentioned_instances = re.findall(r"\b(i-[a-zA-Z0-9_\-]+)\b", stmt_lower)
            if valid_instance_ids:
                unrelated_inst = [inst for inst in mentioned_instances if inst not in valid_instance_ids]
                if unrelated_inst:
                    rejection_reasons.append(f"Ungrounded: Evidence references unrelated EC2 instance ID '{unrelated_inst[0]}' not in target context.")
                    continue

            mentioned_sgs = re.findall(r"\b(sg-[a-zA-Z0-9_\-]+)\b", stmt_lower)
            if valid_sg_ids:
                unrelated_sgs = [sg for sg in mentioned_sgs if sg not in valid_sg_ids]
                if unrelated_sgs:
                    rejection_reasons.append(f"Ungrounded: Evidence references unrelated Security Group ID '{unrelated_sgs[0]}' not in target context.")
                    continue

            mentioned_rtbs = re.findall(r"\b(rtb-[a-zA-Z0-9_\-]+)\b", stmt_lower)
            if valid_rtb_ids:
                unrelated_rtbs = [rtb for rtb in mentioned_rtbs if rtb not in valid_rtb_ids]
                if unrelated_rtbs:
                    rejection_reasons.append(f"Ungrounded: Evidence references unrelated Route Table ID '{unrelated_rtbs[0]}' not in target context.")
                    continue

            # Contradiction Check 8: Irrelevant SG port-absence claims for local service failures.
            # When the context shows a stopped Windows service and host telemetry is present,
            # "No Security Group rule for TCP <port>" evidence is NOT causal — a local service
            # failure (e.g. Spooler stopped) is host-internal and not caused by a missing SG rule.
            if has_host_telemetry and stopped_services:
                sg_port_absence_patterns = [
                    r"no\s+security\s+group\s+rule.{0,40}tcp\s+port\s+(\d+)",
                    r"security\s+group.{0,40}does\s+not\s+allow\s+(?:inbound\s+)?tcp\s+(?:port\s+)?(\d+)",
                    r"security\s+group.{0,40}lacks.{0,30}tcp\s+(?:port\s+)?(\d+)",
                    r"no\s+inbound\s+(?:tcp\s+)?rule.{0,30}(?:port\s+)?(\d+)",
                    r"tcp\s+port\s+(\d+)\s+(?:is\s+)?(?:not\s+allowed|blocked|missing)\s+in\s+(?:the\s+)?security\s+group",
                ]
                for pat in sg_port_absence_patterns:
                    m = re.search(pat, stmt_lower)
                    if m:
                        port_num = int(m.group(1))
                        # Only reject if the port is NOT directly relevant to a web service check
                        # (ports 80/443 are always legitimate SG evidence for web queries)
                        if port_num not in (80, 443):
                            rejection_reasons.append(
                                f"Irrelevant: Evidence claims SG lacks TCP port {port_num}, "
                                f"but context shows a stopped local Windows service. "
                                f"A missing SG rule is not causal evidence for a host-internal service failure."
                            )
                            rejected = True
                            break
            if rejected:
                continue

            # Contradiction Check 9: Irrelevant negative observations (e.g. "No Load Balancer exists", "No Target Group configured")
            # If evidence asserts non-existence of resources (ALB, Target Group, ASG) that are not part of the identified root cause, reject it as non-causal noise.
            negative_obs_patterns = [
                r"\b(no|lacks|without)\b.{0,40}?\b(application\s+load\s+balancer|load\s+balancer|alb|target\s+group|auto\s*scaling\s+group)\b",
                r"\b(application\s+load\s+balancer|load\s+balancer|alb|target\s+group|auto\s*scaling\s+group)\b.{0,40}?\b(does\s+not\s+exist|is\s+not\s+configured|is\s+missing|not\s+found|unconfigured)\b",
            ]
            for pat in negative_obs_patterns:
                if re.search(pat, stmt_lower):
                    rejection_reasons.append(
                        f"Irrelevant: Negative resource observation in evidence '{stmt_clean}' is non-causal to the diagnosis."
                    )
                    rejected = True
                    break
            if rejected:
                continue

            # Contradiction Check 10: Multilingual/CJK text in evidence statement
            if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", stmt_clean):
                rejection_reasons.append(f"Non-English text in evidence statement: '{stmt_clean}'")
                continue

            valid_evidence.append(stmt_clean)

        return valid_evidence, rejection_reasons


    def check_evidence_grounding(
        self,
        diagnosis_data: Dict[str, Any],
        cloud_context: Dict[str, Any],
        rag_texts: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if specific metrics/numbers/ports/IDs mentioned in the evidence or root cause
        are present in the supplied cloud context or RAG texts, and verifies evidence consistency.
        Ensures active resource state strictly overrides historical CloudTrail events.
        Returns (is_grounded, warning_messages).
        """
        context_str = (json.dumps(cloud_context or {}) + " " + " ".join(rag_texts)).lower()
        evidence_items = diagnosis_data.get("evidence", [])
        root_cause = diagnosis_data.get("probable_root_cause", "")
        root_cause_lower = root_cause.lower()

        warnings = []
        is_grounded = True

        # 1. Contradiction and factual consistency filtering for evidence
        valid_ev, rejection_reasons = self.validate_and_filter_evidence(evidence_items, cloud_context)
        if rejection_reasons:
            for r in rejection_reasons:
                if "negative resource observation" not in r.lower():
                    warnings.append(r)
            if len(valid_ev) == 0 and len(evidence_items) > 0:
                is_grounded = False

        # Extract active configuration for root cause contradiction checks
        resources = cloud_context.get("resources", {}) if isinstance(cloud_context, dict) else {}
        signals = cloud_context.get("signals", []) if isinstance(cloud_context, dict) else []

        allowed_ports = set()
        sgs = resources.get("security_groups", []) if isinstance(resources, dict) else []
        if not sgs and isinstance(cloud_context, dict) and "security_groups" in cloud_context:
            sgs = cloud_context.get("security_groups", [])
        for sg in (sgs if isinstance(sgs, list) else []):
            if isinstance(sg, dict):
                for rule in sg.get("inbound_rules", []):
                    if isinstance(rule, dict) and str(rule.get("protocol", "")).lower() in ("tcp", "-1"):
                        from_p = rule.get("from_port")
                        to_p = rule.get("to_port")
                        if from_p is None:
                            allowed_ports.update([80, 443, 22, 3389, 8080, 3306, 5432])
                        elif to_p is not None:
                            for p in range(from_p, min(to_p + 1, from_p + 1000)):
                                allowed_ports.add(p)
                        else:
                            allowed_ports.add(from_p)

        blocked_ports = {
            s.get("value") for s in (signals if isinstance(signals, list) else [])
            if isinstance(s, dict) and s.get("type") == "port_not_allowed" and isinstance(s.get("value"), int)
        }

        # 2. Root Cause Contradiction Check: Claiming port removed/blocked when SG allows it
        for port_num in allowed_ports:
            if port_num not in blocked_ports:
                port_str = str(port_num)
                # Matches: "port 80 was removed", "inbound tcp 80 removed", "missing port 80", "port 80 blocked", "port 80 is not permitted"
                if re.search(rf"\bport\s+{port_str}\b.*?\b(removed|revoked|blocked|missing|not\s+permitted|lacks)\b", root_cause_lower) or \
                   re.search(rf"\b(removed|revoked|blocked|missing|lacks|no\s+inbound)\b.*?\bport\s+{port_str}\b", root_cause_lower) or \
                   re.search(rf"\b(tcp|http|https)\s+{port_str}\s+(?:was\s+)?(?:removed|revoked|blocked|missing)\b", root_cause_lower):
                    warnings.append(
                        f"Contradiction: Root cause claims port {port_num} was removed/blocked in Security Group, but active Security Group configuration allows port {port_num}."
                    )
                    is_grounded = False

        # 3. Root Cause Contradiction Check: Claiming running service is stopped
        hosts = resources.get("host_telemetry", []) if isinstance(resources, dict) else []
        if not hosts and isinstance(cloud_context, dict) and "host_telemetry" in cloud_context:
            hosts = cloud_context.get("host_telemetry", [])
        running_services = set()
        stopped_services = set()
        active_listening_ports = set()
        for h in (hosts if isinstance(hosts, list) else []):
            if isinstance(h, dict):
                for svc in h.get("services", []):
                    if isinstance(svc, dict):
                        n = str(svc.get("name", "")).lower()
                        st = str(svc.get("status", "")).lower()
                        if st == "running":
                            running_services.add(n)
                        elif st in ("stopped", "stop_pending", "paused"):
                            stopped_services.add(n)
                for p in h.get("listening_ports", []):
                    if isinstance(p, dict) and p.get("port") is not None:
                        try:
                            active_listening_ports.add(int(p.get("port")))
                        except (ValueError, TypeError):
                            pass

        for svc in running_services:
            if svc not in stopped_services:
                if re.search(rf"\b{svc}\b.*?\b(is\s+stopped|service\s+stopped|crashed|inactive|was\s+stopped)\b", root_cause_lower) or \
                   re.search(rf"\b(stopped|crashed|inactive)\b.*?\b{svc}\b", root_cause_lower):
                    warnings.append(
                        f"Contradiction: Root cause claims service '{svc}' is stopped, but host telemetry confirms it is Running."
                    )
                    is_grounded = False

        # 4. Root Cause Contradiction Check: Claiming port is not listening when active
        for lp in active_listening_ports:
            if re.search(rf"\bport\s+{lp}\b.*?\b(not\s+listening|not\s+running)\b", root_cause_lower):
                warnings.append(
                    f"Contradiction: Root cause claims port {lp} is not listening, but host telemetry confirms port {lp} is listening."
                )
                is_grounded = False

        combined_claims = " ".join(evidence_items) + " " + root_cause
        
        ports_mentioned = re.findall(r"\bport\s+(\d+)\b", combined_claims, re.IGNORECASE)
        ports_mentioned.extend(re.findall(r"\b(443|80|22|3306|5432|8080)\b", combined_claims))

        for port in set(ports_mentioned):
            if port not in context_str:
                warnings.append(f"Port '{port}' mentioned in diagnosis was not found in context or knowledge.")
                is_grounded = False

        instance_ids = re.findall(r"\b(i-[a-f0-9]{8,17})\b", combined_claims, re.IGNORECASE)
        for inst_id in set(instance_ids):
            if inst_id.lower() not in context_str:
                warnings.append(f"Instance ID '{inst_id}' mentioned in diagnosis was not found in context.")
                is_grounded = False

        # Resource existence check: ALB / Load Balancers
        # Only flag if the model is asserting ALB/TG FAILURE, not merely noting their absence.
        # e.g. "No load balancer or target group exists" is benign and must NOT be flagged.
        combined_lower = combined_claims.lower()
        alb_failure_patterns = [
            r"\b(alb|application\s+load\s+balancer|target\s+group|target_group)\b.{0,60}?\b(is\s+)?(unhealthy|failing|failure|unavailable|not\s+healthy|reporting\s+unhealthy|health\s+check\s+fail)\b",
            r"\b(unhealthy|failing|failure)\b.{0,60}?\b(target\s+group|alb|application\s+load\s+balancer)\b",
            r"\balb\b.{0,80}?\btarget.{0,30}?\b(unhealthy|failing|failure)\b",
        ]
        alb_failure_in_claims = any(re.search(pat, combined_lower) for pat in alb_failure_patterns)
        if alb_failure_in_claims:
            has_albs = bool(
                isinstance(cloud_context, dict)
                and cloud_context.get("resources", {}).get("load_balancers")
            )
            if not has_albs:
                warnings.append("Diagnosis claims Load Balancer / Target Group failure, but no ALB resources exist in live cloud context.")
                is_grounded = False

        # Application Process / IIS Down or Configuration claim check without telemetry
        app_down_keywords = [
            "iis website is down", "iis is down", "application process is down", 
            "web server crashed", "website might be down", "configured to listen", 
            "iis configuration", "no iis instances", "iis website"
        ]
        if any(kw in combined_lower for kw in app_down_keywords):
            has_process_telemetry = any(term in context_str for term in ["process_list", "win32_service", "iis_site_status", "process_status"])
            if not has_process_telemetry:
                warnings.append("Diagnosis claims IIS/application process state or configuration issue, but no host process telemetry exists in live cloud context.")
                is_grounded = False

        # Metric observation claim check without CloudWatch metrics
        metric_claim_keywords = ["detected in the provided metrics", "detected in metrics", "no http traffic"]
        if any(kw in combined_lower for kw in metric_claim_keywords):
            has_metrics = bool(
                isinstance(cloud_context, dict)
                and cloud_context.get("metrics")
            )
            if not has_metrics:
                warnings.append("Diagnosis claims CloudWatch metric evidence, but no metric telemetry exists in live cloud context.")
                is_grounded = False

        return is_grounded, warnings

    def build_insufficient_evidence_response(
        self,
        question: str,
        reason: str = "Insufficient infrastructure evidence or telemetry data available."
    ) -> Dict[str, Any]:
        """
        Build a standardized, low-confidence fallback response when context is missing or invalid.
        """
        return {
            "problem": f"Reported issue: {question}",
            "probable_root_cause": f"Insufficient evidence to determine a single probable root cause. ({reason})",
            "evidence": [],
            "impact": "Operational state cannot be conclusively assessed due to missing cloud telemetry.",
            "recommendation": "Collect additional infrastructure, CloudWatch metric, Security Group, or log data.",
            "confidence": 0.20
        }
