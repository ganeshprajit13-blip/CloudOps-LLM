from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.aws.cloudtrail import get_cloudtrail_events
from app.aws.cloudwatch import get_cloudwatch_metrics
from app.aws.ec2 import get_ec2_instances
from app.aws.load_balancer import get_load_balancers
from app.aws.security_groups import get_security_groups
from app.aws.vpc import get_vpc_resources
from app.main import app
from app.services.aws_collector import collect_infrastructure_data

client = TestClient(app)


# --- EC2 Tests ---
@patch("app.aws.ec2.get_ec2_client")
def test_get_ec2_instances_success(mock_get_client):
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "State": {"Name": "running"},
                            "InstanceType": "t3.micro",
                            "PrivateIpAddress": "10.0.1.15",
                            "PublicIpAddress": "54.210.10.20",
                            "Placement": {"AvailabilityZone": "ap-south-1a"},
                            "SubnetId": "subnet-1111",
                            "VpcId": "vpc-2222",
                            "SecurityGroups": [{"GroupId": "sg-3333"}],
                            "ImageId": "ami-4444",
                            "LaunchTime": datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
                            "Tags": [{"Key": "Name", "Value": "WebServer"}],
                        }
                    ]
                }
            ]
        }
    ]
    mock_client.get_paginator.return_value = mock_paginator
    mock_get_client.return_value = mock_client

    instances = get_ec2_instances("ap-south-1")
    assert len(instances) == 1
    assert instances[0]["instance_id"] == "i-1234567890abcdef0"
    assert instances[0]["state"] == "running"
    assert instances[0]["security_group_ids"] == ["sg-3333"]
    assert instances[0]["tags"]["Name"] == "WebServer"


@patch("app.aws.ec2.get_ec2_client")
def test_get_ec2_instances_empty(mock_get_client):
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"Reservations": []}]
    mock_client.get_paginator.return_value = mock_paginator
    mock_get_client.return_value = mock_client

    instances = get_ec2_instances("ap-south-1")
    assert instances == []


# --- CloudWatch Tests ---
@patch("app.aws.cloudwatch.get_cloudwatch_client")
def test_get_cloudwatch_metrics_success(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_metric_statistics.return_value = {
        "Datapoints": [
            {
                "Timestamp": datetime(2026, 9, 8, 11, 0, tzinfo=timezone.utc),
                "Average": 45.2,
                "Maximum": 88.1,
                "Unit": "Percent",
            }
        ]
    }
    mock_get_client.return_value = mock_client

    metrics = get_cloudwatch_metrics(resource_id="i-12345", metric_names=["CPUUtilization"])
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "CPUUtilization"
    assert metrics[0]["average"] == 45.2


# --- CloudTrail Tests ---
@patch("app.aws.cloudtrail.get_cloudtrail_client")
def test_get_cloudtrail_events_success(mock_get_client):
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Events": [
                {
                    "EventId": "evt-001",
                    "EventTime": datetime(2026, 9, 8, 10, 30, tzinfo=timezone.utc),
                    "EventName": "AuthorizeSecurityGroupIngress",
                    "EventSource": "ec2.amazonaws.com",
                    "Username": "admin-user",
                    "Resources": [{"ResourceType": "AWS::EC2::SecurityGroup", "ResourceName": "sg-3333"}],
                }
            ]
        }
    ]
    mock_client.get_paginator.return_value = mock_paginator
    mock_client.meta.region_name = "ap-south-1"
    mock_get_client.return_value = mock_client

    events = get_cloudtrail_events(hours=1)
    assert len(events) == 1
    assert events[0]["event_name"] == "AuthorizeSecurityGroupIngress"
    assert events[0]["username"] == "admin-user"


# --- VPC Tests ---
@patch("app.aws.vpc.get_ec2_client")
def test_get_vpc_resources_success(mock_get_client):
    mock_client = MagicMock()
    mock_client.describe_vpcs.return_value = {"Vpcs": [{"VpcId": "vpc-111", "CidrBlock": "10.0.0.0/16", "IsDefault": True, "State": "available"}]}
    mock_client.describe_subnets.return_value = {"Subnets": [{"SubnetId": "subnet-111", "VpcId": "vpc-111", "CidrBlock": "10.0.1.0/24", "AvailabilityZone": "ap-south-1a", "AvailableIpAddressCount": 250, "MapPublicIpOnLaunch": True}]}
    mock_client.describe_route_tables.return_value = {"RouteTables": [{"RouteTableId": "rtb-111", "VpcId": "vpc-111", "Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-111", "State": "active"}], "Associations": []}]}
    mock_client.describe_internet_gateways.return_value = {"InternetGateways": [{"InternetGatewayId": "igw-111", "Attachments": [{"VpcId": "vpc-111", "State": "available"}]}]}
    mock_client.describe_nat_gateways.return_value = {"NatGateways": []}
    mock_get_client.return_value = mock_client

    vpc_data = get_vpc_resources("ap-south-1")
    assert len(vpc_data["vpcs"]) == 1
    assert len(vpc_data["subnets"]) == 1
    assert len(vpc_data["route_tables"]) == 1
    assert len(vpc_data["internet_gateways"]) == 1
    assert vpc_data["vpcs"][0]["vpc_id"] == "vpc-111"


# --- Security Group Tests ---
@patch("app.aws.security_groups.get_ec2_client")
def test_get_security_groups_success(mock_get_client):
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "SecurityGroups": [
                {
                    "GroupId": "sg-web",
                    "GroupName": "web-sg",
                    "Description": "Allow HTTPS",
                    "VpcId": "vpc-111",
                    "IpPermissions": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 443,
                            "ToPort": 443,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        }
                    ],
                    "IpPermissionsEgress": [],
                }
            ]
        }
    ]
    mock_client.get_paginator.return_value = mock_paginator
    mock_get_client.return_value = mock_client

    sgs = get_security_groups("ap-south-1")
    assert len(sgs) == 1
    assert sgs[0]["group_id"] == "sg-web"
    assert sgs[0]["inbound_rules"][0]["from_port"] == 443
    assert sgs[0]["inbound_rules"][0]["sources"] == ["0.0.0.0/0"]


# --- Load Balancer Tests ---
@patch("app.aws.load_balancer.get_elbv2_client")
def test_get_load_balancers_success(mock_get_client):
    mock_client = MagicMock()
    lb_paginator = MagicMock()
    lb_paginator.paginate.return_value = [
        {
            "LoadBalancers": [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-south-1:1234:loadbalancer/app/my-alb/50",
                    "LoadBalancerName": "my-alb",
                    "Type": "application",
                    "State": {"Code": "active"},
                    "DNSName": "my-alb-123.ap-south-1.elb.amazonaws.com",
                    "VpcId": "vpc-111",
                    "AvailabilityZones": [{"ZoneName": "ap-south-1a"}],
                }
            ]
        }
    ]
    tg_paginator = MagicMock()
    tg_paginator.paginate.return_value = [
        {
            "TargetGroups": [
                {
                    "TargetGroupArn": "arn:aws:tg:123",
                    "TargetGroupName": "my-tg",
                    "Protocol": "HTTP",
                    "Port": 80,
                    "VpcId": "vpc-111",
                    "HealthCheckProtocol": "HTTP",
                    "HealthCheckPort": "80",
                    "HealthCheckPath": "/health",
                }
            ]
        }
    ]

    mock_client.get_paginator.side_effect = lambda action: lb_paginator if action == "describe_load_balancers" else tg_paginator
    mock_client.describe_target_health.return_value = {
        "TargetHealthDescriptions": [
            {
                "Target": {"Id": "i-12345", "Port": 80},
                "TargetHealth": {"State": "healthy", "Reason": None, "Description": None},
            }
        ]
    }
    mock_get_client.return_value = mock_client

    lbs = get_load_balancers("ap-south-1")
    assert len(lbs) == 1
    assert lbs[0]["name"] == "my-alb"
    assert len(lbs[0]["target_groups"]) == 1
    assert lbs[0]["target_groups"][0]["target_health"][0]["health_state"] == "healthy"


# --- Service Collector Test ---
@patch("app.services.aws_collector.get_ec2_instances")
@patch("app.services.aws_collector.get_cloudwatch_metrics")
@patch("app.services.aws_collector.get_cloudtrail_events")
@patch("app.services.aws_collector.get_vpc_resources")
@patch("app.services.aws_collector.get_security_groups")
@patch("app.services.aws_collector.get_load_balancers")
def test_collect_infrastructure_data(mock_alb, mock_sg, mock_vpc, mock_ct, mock_cw, mock_ec2):
    mock_ec2.return_value = [{"instance_id": "i-1"}]
    mock_cw.return_value = []
    mock_ct.return_value = []
    mock_vpc.return_value = {"vpcs": [], "subnets": [], "route_tables": [], "internet_gateways": [], "nat_gateways": []}
    mock_sg.return_value = []
    mock_alb.return_value = []

    data = collect_infrastructure_data("ap-south-1")
    assert data["region"] == "ap-south-1"
    assert len(data["ec2"]) == 1
    assert data["ec2"][0]["instance_id"] == "i-1"


# --- API Route Tests ---
@patch("app.api.routes.aws.get_sts_identity")
def test_api_get_sts_route(mock_get_sts):
    mock_get_sts.return_value = {
        "status": "authenticated",
        "account_id": "123456789012",
        "arn": "arn:aws:iam::123456789012:user/test-user",
        "user_id": "AIDA12345",
        "region": "eu-north-1",
    }
    response = client.get("/api/aws/sts")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "authenticated"
    assert json_data["account_id"] == "123456789012"


@patch("app.api.routes.aws.get_ec2_instances")
def test_api_get_ec2_route(mock_get_ec2):
    mock_get_ec2.return_value = [
        {
            "instance_id": "i-test",
            "state": "running",
            "instance_type": "t3.micro",
            "private_ip": "10.0.0.1",
            "public_ip": None,
            "availability_zone": "ap-south-1a",
            "subnet_id": "sub-1",
            "vpc_id": "vpc-1",
            "security_group_ids": [],
            "ami_id": "ami-1",
            "launch_time": None,
            "tags": {},
        }
    ]
    response = client.get("/api/aws/ec2?region=ap-south-1")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["region"] == "ap-south-1"
    assert len(json_data["instances"]) == 1
    assert json_data["instances"][0]["instance_id"] == "i-test"


@patch("app.api.routes.aws.collect_infrastructure_data")
def test_api_get_infrastructure_route(mock_collect):
    mock_collect.return_value = {
        "region": "ap-south-1",
        "timestamp": "2026-09-08T11:00:00+00:00",
        "ec2": [],
        "host_telemetry": [],
        "cloudwatch": [],
        "cloudtrail": [],
        "vpc": {"vpcs": [], "subnets": [], "route_tables": [], "internet_gateways": [], "nat_gateways": []},
        "security_groups": [],
        "load_balancers": [],
    }
    response = client.get("/api/aws/infrastructure?region=ap-south-1")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["region"] == "ap-south-1"
    assert "timestamp" in json_data


# --- SSM Host Telemetry Tests ---
@patch("app.aws.ssm.get_ssm_client")
def test_get_windows_host_telemetry_success(mock_get_client):
    from app.aws.ssm import get_windows_host_telemetry
    mock_client = MagicMock()
    mock_client.send_command.return_value = {"Command": {"CommandId": "cmd-12345"}}

    json_mock_output = (
        '{"Services":[{"Name":"W3SVC","DisplayName":"World Wide Web Publishing Service","Status":"Stopped","StartType":"Automatic"}],'
        '"ListeningPorts":[{"LocalPort":80,"LocalAddress":"0.0.0.0","State":"Listen","OwningProcess":4}],'
        '"SystemInfo":{"Caption":"Microsoft Windows Server 2022 Datacenter","Version":"10.0.20348","LastBootUpTime":"20260908120000.000000+000","TotalVisibleMemorySize":4193808,"FreePhysicalMemory":2540000}}'
    )
    mock_client.get_command_invocation.return_value = {
        "Status": "Success",
        "StandardOutputContent": json_mock_output,
    }



    mock_get_client.return_value = mock_client

    telemetry = get_windows_host_telemetry(instance_ids=["i-1234567890abcdef0"], region="eu-north-1")
    assert len(telemetry) == 1
    record = telemetry[0]
    assert record["instance_id"] == "i-1234567890abcdef0"
    assert record["platform"] == "windows"
    assert len(record["services"]) == 1
    assert record["services"][0]["name"] == "W3SVC"
    assert record["services"][0]["status"] == "Stopped"
    assert record["services"][0]["start_type"] == "Automatic"
    assert record["system_info"]["os_name"] == "Microsoft Windows Server 2022 Datacenter"


@patch("app.aws.ssm.get_ssm_client")
def test_get_windows_host_telemetry_inventory_fallback(mock_get_client):
    from app.aws.ssm import get_windows_host_telemetry
    from botocore.exceptions import ClientError
    mock_client = MagicMock()
    mock_client.send_command.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}}, "SendCommand"
    )
    mock_client.list_inventory_entries.return_value = {
        "Entries": [
            {"Name": "W3SVC", "DisplayName": "World Wide Web Publishing Service", "Status": "Stopped", "StartMode": "Auto"}
        ]
    }
    mock_get_client.return_value = mock_client

    telemetry = get_windows_host_telemetry(instance_ids=["i-12345"], region="eu-north-1")
    assert len(telemetry) == 1
    assert telemetry[0]["collection_method"] == "ssm_inventory"
    assert telemetry[0]["services"][0]["name"] == "W3SVC"
    assert telemetry[0]["services"][0]["status"] == "Stopped"


@patch("app.api.routes.aws.get_windows_host_telemetry")
def test_api_get_host_telemetry_route(mock_get_host):
    mock_get_host.return_value = [
        {
            "instance_id": "i-test-win",
            "platform": "windows",
            "collection_method": "ssm_run_command",
            "services": [
                {
                    "name": "W3SVC",
                    "display_name": "World Wide Web Publishing Service",
                    "status": "Stopped",
                    "start_type": "Automatic",
                }
            ],
            "listening_ports": [],
            "system_info": {"os_name": "Windows Server 2022"},
            "error": None,
        }
    ]
    response = client.get("/api/aws/host-telemetry?instance_id=i-test-win&region=eu-north-1")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["region"] == "eu-north-1"
    assert len(json_data["host_telemetry"]) == 1
    assert json_data["host_telemetry"][0]["services"][0]["name"] == "W3SVC"
    assert json_data["host_telemetry"][0]["services"][0]["status"] == "Stopped"


@patch("app.aws.cloudwatch.get_cloudwatch_client")
def test_get_cloudwatch_metrics_with_instance_ids(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_metric_statistics.return_value = {
        "Datapoints": [
            {
                "Timestamp": datetime(2026, 9, 13, 0, 15, tzinfo=timezone.utc),
                "Average": 50.0,
                "Maximum": 99.8,
                "Unit": "Percent",
            }
        ]
    }
    mock_get_client.return_value = mock_client

    metrics = get_cloudwatch_metrics(instance_ids=["i-07243bdf548e18f5b"], metric_names=["CPUUtilization"])
    assert len(metrics) == 1
    assert metrics[0]["resource_id"] == "i-07243bdf548e18f5b"
    assert metrics[0]["maximum"] == 99.8
    assert metrics[0]["average"] == 50.0

    mock_client.get_metric_statistics.assert_called_once()
    call_kwargs = mock_client.get_metric_statistics.call_args[1]
    assert call_kwargs["Dimensions"] == [{"Name": "InstanceId", "Value": "i-07243bdf548e18f5b"}]
    assert call_kwargs["Namespace"] == "AWS/EC2"
    assert call_kwargs["MetricName"] == "CPUUtilization"
    assert "Average" in call_kwargs["Statistics"]
    assert "Maximum" in call_kwargs["Statistics"]


