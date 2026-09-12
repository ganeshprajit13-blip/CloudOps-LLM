import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.services.context_builder import ContextBuilder

@pytest.fixture
def sample_cloud_context():
    return {
        "summary": {
            "total_instances": 2,
            "running_instances": 2,
            "high_cpu_instances": 0,
            "unhealthy_targets": 1
        },
        "resources": {
            "ec2": [
                {
                    "instance_id": "i-01112223334445556",
                    "state": "running",
                    "instance_type": "t3.medium",
                    "public_ip": "54.210.10.1",
                    "private_ip": "10.0.1.50",
                    "subnet_id": "subnet-public-1a",
                    "security_group_ids": ["sg-012345"]
                },
                {
                    "instance_id": "i-09998887776665554",
                    "state": "running",
                    "instance_type": "t3.large",
                    "public_ip": "54.210.10.2",
                    "private_ip": "10.0.1.51",
                    "subnet_id": "subnet-public-1b",
                    "security_group_ids": ["sg-099999"]
                }
            ],
            "security_groups": [
                {
                    "group_id": "sg-012345",
                    "name": "web-sg",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}
                    ]
                }
            ]
        },
        "signals": [
            {
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": "i-01112223334445556",
                "description": "Port 443 inbound is not permitted by Security Group sg-012345."
            }
        ]
    }


def test_context_builder_formatting(sample_cloud_context):
    builder = ContextBuilder()
    formatted = builder.build_context_text(sample_cloud_context)

    assert "CURRENT CLOUD STATE" in formatted
    assert "DETECTED SIGNALS" in formatted
    assert "NETWORK CONFIGURATION" in formatted
    assert "SECURITY CONFIGURATION" in formatted
    assert "LOAD BALANCER INFORMATION" in formatted
    assert "i-01112223334445556" in formatted
    assert "port_not_allowed" in formatted


def test_context_builder_resource_filtering(sample_cloud_context):
    builder = ContextBuilder()
    
    # Filter by specific instance ID
    filtered_context = builder.filter_context_by_resource(sample_cloud_context, "i-01112223334445556")
    formatted = builder.build_context_text(filtered_context, resource_id="i-01112223334445556")

    assert "i-01112223334445556" in formatted
    assert "i-09998887776665554" not in formatted


def test_context_builder_empty_context():
    builder = ContextBuilder()
    formatted = builder.build_context_text({})
    assert "No live cloud context available" in formatted


def test_context_builder_excludes_unrelated_security_groups_and_route_tables():
    builder = ContextBuilder()
    full_context = {
        "summary": {},
        "resources": {
            "ec2": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "state": "running",
                    "instance_type": "t3.medium",
                    "public_ip": "13.51.10.20",
                    "private_ip": "172.31.10.5",
                    "vpc_id": "vpc-0595e363d1e0a55de",
                    "subnet_id": "subnet-023c32953cefa4583",
                    "security_group_ids": ["sg-0508c38f4cfa83f82"]
                },
                {
                    "instance_id": "i-other999",
                    "state": "running",
                    "vpc_id": "vpc-other",
                    "subnet_id": "subnet-other",
                    "security_group_ids": ["sg-other"]
                }
            ],
            "security_groups": [
                {
                    "group_id": "sg-0508c38f4cfa83f82",
                    "name": "CloudOps-Test-SG",
                    "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}]
                },
                {
                    "group_id": "sg-0b5463631438f138c",
                    "name": "launch-wizard-1",
                    "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}]
                }
            ],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "platform": "windows",
                    "services": [{"name": "W3SVC", "status": "Running", "start_type": "Automatic"}],
                    "listening_ports": [{"port": 80, "state": "Listen"}]
                },
                {
                    "instance_id": "i-other999",
                    "platform": "windows",
                    "services": [{"name": "Spooler", "status": "Running", "start_type": "Automatic"}],
                    "listening_ports": [{"port": 8080, "state": "Listen"}]
                }
            ],
            "vpc": {
                "subnets": [
                    {"subnet_id": "subnet-023c32953cefa4583", "vpc_id": "vpc-0595e363d1e0a55de"},
                    {"subnet_id": "subnet-other", "vpc_id": "vpc-other"}
                ],
                "route_tables": [
                    {
                        "route_table_id": "rtb-0030d6154d6dc1f0f",
                        "vpc_id": "vpc-0595e363d1e0a55de",
                        "routes": [{"destination": "0.0.0.0/0", "target": "igw-0f521f4b0d8c2ff66"}],
                        "associations": [{"main": True, "subnet_id": None}]
                    },
                    {
                        "route_table_id": "rtb-05bde2c85ad53577c",
                        "vpc_id": "vpc-other",
                        "routes": [{"destination": "10.0.0.0/16", "target": "local"}],
                        "associations": [{"main": True, "subnet_id": None}]
                    }
                ]
            }
        },
        "signals": [
            {
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": "i-07243bdf548e18f5b",
                "description": "Security Group sg-0508c38f4cfa83f82 does not allow inbound TCP 443 (HTTPS) traffic.",
                "value": 443,
                "metadata": {"group_id": "sg-0508c38f4cfa83f82"}
            },
            {
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": "sg-0b5463631438f138c",
                "description": "Security Group sg-0b5463631438f138c does not allow inbound TCP 443 (HTTPS) traffic.",
                "value": 443,
                "metadata": {"group_id": "sg-0b5463631438f138c"}
            },
            {
                "type": "missing_default_route",
                "severity": "high",
                "resource_id": "rtb-05bde2c85ad53577c",
                "description": "Route Table rtb-05bde2c85ad53577c has no default route (0.0.0.0/0) to an Internet Gateway or NAT Gateway.",
                "value": "missing_default_route",
                "metadata": {"route_table_id": "rtb-05bde2c85ad53577c", "vpc_id": "vpc-other"}
            }
        ],
        "cloudtrail_events": [
            {
                "event_name": "AuthorizeSecurityGroupIngress",
                "resource": "sg-0508c38f4cfa83f82",
                "principal": "admin"
            },
            {
                "event_name": "AuthorizeSecurityGroupIngress",
                "resource": "sg-other",
                "principal": "admin"
            }
        ]
    }

    filtered = builder.filter_context_by_resource(full_context, "i-07243bdf548e18f5b")
    formatted_text = builder.build_context_text(filtered, resource_id="i-07243bdf548e18f5b")

    # Target EC2 and attached SG retained
    assert "i-07243bdf548e18f5b" in formatted_text
    assert "sg-0508c38f4cfa83f82" in formatted_text
    assert "W3SVC" in formatted_text

    # Unrelated resources excluded
    assert "i-other999" not in formatted_text
    assert "sg-0b5463631438f138c" not in formatted_text
    assert "rtb-05bde2c85ad53577c" not in formatted_text
    assert "sg-other" not in formatted_text

    # Verify signals and evidence in filtered object
    signal_types = [s["resource_id"] for s in filtered["signals"]]
    assert "sg-0b5463631438f138c" not in signal_types
    assert "rtb-05bde2c85ad53577c" not in signal_types
    assert len(filtered["resources"]["security_groups"]) == 1
    assert filtered["resources"]["security_groups"][0]["group_id"] == "sg-0508c38f4cfa83f82"

