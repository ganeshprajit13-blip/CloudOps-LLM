"""
CloudOps Resource ID Resolver
==============================
Resolves infrastructure resource IDs from multiple possible field names and
question text. Never invents IDs. Returns a structured result that the caller
can trust completely.

Designed to handle:
- Explicitly passed resource_id
- Non-standard field names (resourceId, resourceID, id, instance_id, …)
- EC2/resource IDs embedded in the user question text
- Cloud context where the resource appears under various keys
- Completely unknown/missing resource (returns unresolved state, not a guess)
"""

import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cloudops.services.resource_resolver")

# ── AWS resource ID regex patterns ──────────────────────────────────────────
# These are deterministic patterns — no guessing.
_EC2_INSTANCE_PATTERN = re.compile(r"\bi-[0-9a-f]{8,17}\b", re.IGNORECASE)
_SG_PATTERN = re.compile(r"\bsg-[0-9a-f]{8,17}\b", re.IGNORECASE)
_VPC_PATTERN = re.compile(r"\bvpc-[0-9a-f]{8,17}\b", re.IGNORECASE)
_SUBNET_PATTERN = re.compile(r"\bsubnet-[0-9a-f]{8,17}\b", re.IGNORECASE)
_RT_PATTERN = re.compile(r"\brtb-[0-9a-f]{8,17}\b", re.IGNORECASE)
_IGW_PATTERN = re.compile(r"\bigw-[0-9a-f]{8,17}\b", re.IGNORECASE)
_NAT_PATTERN = re.compile(r"\bnat-[0-9a-f]{8,17}\b", re.IGNORECASE)
_ELB_PATTERN = re.compile(r"\bapp/[a-zA-Z0-9\-]+/[0-9a-f]{16}\b")

# Ordered list of (pattern, resource_type) for question extraction
_QUESTION_PATTERNS: List[tuple] = [
    (_EC2_INSTANCE_PATTERN, "ec2_instance"),
    (_SG_PATTERN, "security_group"),
    (_VPC_PATTERN, "vpc"),
    (_SUBNET_PATTERN, "subnet"),
    (_RT_PATTERN, "route_table"),
    (_IGW_PATTERN, "internet_gateway"),
    (_NAT_PATTERN, "nat_gateway"),
    (_ELB_PATTERN, "load_balancer"),
]

# All field names to check, in priority order
_RESOURCE_ID_FIELD_CANDIDATES = [
    "resource_id",
    "instance_id",
    "resourceId",
    "resourceID",
    "id",
    "resource",
    "InstanceId",
    "ec2_instance_id",
    "target_id",
    "group_id",
]

_RESOURCE_NAME_FIELD_CANDIDATES = [
    "resource_name",
    "name",
    "resourceName",
    "display_name",
    "Name",
    "tag_name",
]

_RESOURCE_TYPE_FIELD_CANDIDATES = [
    "resource_type",
    "type",
    "resourceType",
    "service",
    "kind",
]


def _infer_resource_type(resource_id: str) -> str:
    """Infer resource type from ID prefix pattern."""
    if not resource_id:
        return "unknown"
    rid = resource_id.lower()
    if rid.startswith("i-"):
        return "ec2_instance"
    if rid.startswith("sg-"):
        return "security_group"
    if rid.startswith("vpc-"):
        return "vpc"
    if rid.startswith("subnet-"):
        return "subnet"
    if rid.startswith("rtb-"):
        return "route_table"
    if rid.startswith("igw-"):
        return "internet_gateway"
    if rid.startswith("nat-"):
        return "nat_gateway"
    if rid.startswith("app/"):
        return "load_balancer"
    return "unknown"


def _extract_ids_from_text(text: str) -> List[Dict[str, str]]:
    """Extract all AWS resource IDs from free text. Returns list of {id, type}."""
    if not text:
        return []
    results = []
    seen = set()
    for pattern, rtype in _QUESTION_PATTERNS:
        for match in pattern.finditer(text):
            rid = match.group(0)
            if rid.lower() not in seen:
                seen.add(rid.lower())
                results.append({"resource_id": rid, "resource_type": rtype})
    return results


def _pick_from_dict(d: dict, candidates: List[str]) -> Optional[str]:
    """Return the first non-empty string value found from a list of candidate keys."""
    if not isinstance(d, dict):
        return None
    for key in candidates:
        val = d.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return None


def resolve_resource_id(
    resource_id: Optional[str] = None,
    cloud_context: Optional[Dict[str, Any]] = None,
    question: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve a resource ID from multiple possible sources.

    Priority:
    1. Explicit resource_id argument (if non-empty)
    2. extra_data dict (non-standard field names)
    3. cloud_context top-level fields
    4. EC2/resource IDs extracted from question text
    5. First EC2 instance in cloud_context resources
    6. Unresolved (resource_id=None, no hallucination)

    Returns:
        {
            "resource_id": str | None,
            "resource_type": str,
            "resource_name": str | None,
            "source": str,         # where it was found
            "path": str | None,    # file path if from file metadata
            "status": "resolved" | "resource_unresolved",
            "candidates": [...]    # alternative IDs found, if any
        }
    """
    cloud_context = cloud_context or {}
    extra_data = extra_data or {}

    # ── 1. Explicit resource_id argument ────────────────────────────────────
    if resource_id and resource_id.strip():
        rid = resource_id.strip()
        rtype = _infer_resource_type(rid)
        logger.debug(f"ResourceResolver: resolved from explicit arg: {rid}")
        return {
            "resource_id": rid,
            "resource_type": rtype,
            "resource_name": None,
            "source": "explicit_argument",
            "path": None,
            "status": "resolved",
            "candidates": [],
        }

    # ── 2. extra_data non-standard field names ───────────────────────────────
    if extra_data:
        rid = _pick_from_dict(extra_data, _RESOURCE_ID_FIELD_CANDIDATES)
        if rid:
            rname = _pick_from_dict(extra_data, _RESOURCE_NAME_FIELD_CANDIDATES)
            rtype = _pick_from_dict(extra_data, _RESOURCE_TYPE_FIELD_CANDIDATES) or _infer_resource_type(rid)
            fpath = extra_data.get("path") or extra_data.get("file_path") or extra_data.get("filePath")
            logger.debug(f"ResourceResolver: resolved from extra_data: {rid}")
            return {
                "resource_id": rid,
                "resource_type": rtype,
                "resource_name": rname,
                "source": "extra_data",
                "path": fpath if isinstance(fpath, str) else None,
                "status": "resolved",
                "candidates": [],
            }

    # ── 3. cloud_context top-level fields ───────────────────────────────────
    if cloud_context:
        rid = _pick_from_dict(cloud_context, _RESOURCE_ID_FIELD_CANDIDATES)
        if rid:
            rtype = _pick_from_dict(cloud_context, _RESOURCE_TYPE_FIELD_CANDIDATES) or _infer_resource_type(rid)
            rname = _pick_from_dict(cloud_context, _RESOURCE_NAME_FIELD_CANDIDATES)
            logger.debug(f"ResourceResolver: resolved from cloud_context top-level: {rid}")
            return {
                "resource_id": rid,
                "resource_type": rtype,
                "resource_name": rname,
                "source": "cloud_context_top_level",
                "path": None,
                "status": "resolved",
                "candidates": [],
            }

    # ── 4. Extract from question text ────────────────────────────────────────
    text_candidates: List[Dict[str, str]] = []
    if question:
        text_candidates = _extract_ids_from_text(question)
    if text_candidates:
        primary = text_candidates[0]
        logger.debug(f"ResourceResolver: extracted from question text: {primary['resource_id']}")
        return {
            "resource_id": primary["resource_id"],
            "resource_type": primary["resource_type"],
            "resource_name": None,
            "source": "question_text_extraction",
            "path": None,
            "status": "resolved",
            "candidates": text_candidates[1:],
        }

    # ── 5. First EC2 instance in cloud_context resources ────────────────────
    resources = cloud_context.get("resources", {}) if isinstance(cloud_context, dict) else {}
    if isinstance(resources, dict):
        ec2_list = resources.get("ec2", [])
        if ec2_list and isinstance(ec2_list[0], dict):
            rid = ec2_list[0].get("instance_id") or ec2_list[0].get("id")
            if rid and isinstance(rid, str) and rid.strip():
                rname = ec2_list[0].get("name") or ec2_list[0].get("Name")
                logger.debug(f"ResourceResolver: resolved from first EC2 in context: {rid}")
                return {
                    "resource_id": rid.strip(),
                    "resource_type": "ec2_instance",
                    "resource_name": rname if isinstance(rname, str) else None,
                    "source": "cloud_context_ec2_list",
                    "path": None,
                    "status": "resolved",
                    "candidates": [
                        {"resource_id": inst.get("instance_id", ""), "resource_type": "ec2_instance"}
                        for inst in ec2_list[1:4]
                        if isinstance(inst, dict) and inst.get("instance_id")
                    ],
                }

    # ── 6. Unresolved — never hallucinate ───────────────────────────────────
    logger.info("ResourceResolver: resource ID could not be resolved from any source")
    return {
        "resource_id": None,
        "resource_type": "unknown",
        "resource_name": None,
        "source": "unresolved",
        "path": None,
        "status": "resource_unresolved",
        "message": "Unable to resolve the affected resource ID from available evidence.",
        "candidates": [],
    }


def resolve_resource_id_from_context_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience wrapper: resolve from a single dict (e.g. a log entry,
    a Dropbox file metadata dict, or an incident payload).
    Delegates to resolve_resource_id() with item as extra_data.
    """
    return resolve_resource_id(
        resource_id=None,
        cloud_context=None,
        question=item.get("content") or item.get("text") or item.get("body"),
        extra_data=item,
    )
