import os
from typing import Dict, Any
from app.aws.client import get_sts_client
from app.core.config import settings
from app.core.logging import logger


def check_credential_status() -> Dict[str, Any]:
    """
    Returns safe boolean presence check of credentials.
    NEVER returns actual credential values.
    """
    has_access_key = bool(settings.AWS_ACCESS_KEY_ID or os.environ.get("AWS_ACCESS_KEY_ID"))
    has_secret_key = bool(settings.AWS_SECRET_ACCESS_KEY or os.environ.get("AWS_SECRET_ACCESS_KEY"))
    region = settings.AWS_REGION or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-north-1"

    return {
        "access_key_configured": has_access_key,
        "secret_key_configured": has_secret_key,
        "region": region,
    }


def get_sts_identity(region: str | None = None) -> Dict[str, Any]:
    """
    Executes get_caller_identity to verify AWS authentication.
    Returns safe identity fields (status, account_id, arn, user_id, region, credentials).
    NEVER returns access keys or secret keys.
    """
    r = region or settings.AWS_REGION
    logger.info(f"Checking AWS STS caller identity in region: {r}")
    cred_status = check_credential_status()

    sts_client = get_sts_client(r)
    res = sts_client.get_caller_identity()

    return {
        "status": "authenticated",
        "account_id": res.get("Account"),
        "arn": res.get("Arn"),
        "user_id": res.get("UserId"),
        "region": r,
        "credentials": cred_status,
    }
