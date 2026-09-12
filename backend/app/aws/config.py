from typing import Any, Dict, List
from botocore.exceptions import ClientError
from app.aws.client import get_config_client
from app.core.logging import logger


def get_config_rules(region: str | None = None) -> List[Dict[str, Any]]:
    """Placeholder interface for read-only AWS Config rules collection."""
    logger.info("Starting read-only AWS Config collection")
    try:
        client = get_config_client(region)
        resp = client.describe_config_rules()
        rules = [
            {
                "config_rule_name": r.get("ConfigRuleName"),
                "config_rule_state": r.get("ConfigRuleState"),
                "description": r.get("Description"),
            }
            for r in resp.get("ConfigRules", [])
        ]
        return rules
    except (RuntimeError, ClientError) as e:
        logger.warning(f"AWS Config collection unavailable or unconfigured: {e}")
        return []
