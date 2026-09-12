import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError
from app.core.config import settings
from app.core.logging import logger


class AWSClientFactory:
    """Factory providing lazy creation of read-only Boto3 clients."""

    def __init__(self, region_name: str | None = None):
        self.region_name = (
            region_name
            or settings.AWS_REGION
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "eu-north-1"
        )

    def get_client(self, service_name: str):
        """Initializes and returns a Boto3 client for the given service."""
        try:
            kwargs = {"region_name": self.region_name}
            
            # Use Settings credentials if configured
            access_key = settings.AWS_ACCESS_KEY_ID or os.environ.get("AWS_ACCESS_KEY_ID")
            secret_key = settings.AWS_SECRET_ACCESS_KEY or os.environ.get("AWS_SECRET_ACCESS_KEY")
            session_token = settings.AWS_SESSION_TOKEN or os.environ.get("AWS_SESSION_TOKEN")

            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key
                if session_token:
                    kwargs["aws_session_token"] = session_token

            return boto3.client(service_name, **kwargs)
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"AWS credentials not configured or incomplete: {e}")
            raise RuntimeError("AWS credentials are not configured or incomplete.") from e
        except BotoCoreError as e:
            logger.error(f"Failed to create Boto3 client for {service_name}: {e}")
            raise RuntimeError(f"Failed to initialize AWS client for {service_name}.") from e


aws_factory = AWSClientFactory()


def get_ec2_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("ec2")


def get_cloudwatch_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("cloudwatch")


def get_cloudtrail_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("cloudtrail")


def get_elbv2_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("elbv2")


def get_config_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("config")


def get_sts_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("sts")


def get_ssm_client(region: str | None = None):
    factory = AWSClientFactory(region) if region else aws_factory
    return factory.get_client("ssm")

