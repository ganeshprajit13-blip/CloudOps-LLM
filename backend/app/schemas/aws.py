from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# EC2 Schemas
class EC2InstanceSchema(BaseModel):
    instance_id: Optional[str] = None
    state: Optional[str] = None
    instance_type: Optional[str] = None
    private_ip: Optional[str] = None
    public_ip: Optional[str] = None
    availability_zone: Optional[str] = None
    subnet_id: Optional[str] = None
    vpc_id: Optional[str] = None
    security_group_ids: List[str] = Field(default_factory=list)
    ami_id: Optional[str] = None
    launch_time: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class EC2ResponseSchema(BaseModel):
    region: str
    instances: List[EC2InstanceSchema]


# CloudWatch Schemas
class CloudWatchMetricSchema(BaseModel):
    metric_name: str
    resource_id: str
    timestamp: Optional[str] = None
    average: Optional[float] = None
    maximum: Optional[float] = None
    unit: Optional[str] = None


class CloudWatchResponseSchema(BaseModel):
    region: str
    metrics: List[CloudWatchMetricSchema]


# CloudTrail Schemas
class CloudTrailResourceSchema(BaseModel):
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None


class CloudTrailEventSchema(BaseModel):
    event_id: Optional[str] = None
    event_time: Optional[str] = None
    event_name: Optional[str] = None
    event_source: Optional[str] = None
    username: Optional[str] = None
    resources: List[CloudTrailResourceSchema] = Field(default_factory=list)
    aws_region: Optional[str] = None
    access_key_id: Optional[str] = None


class CloudTrailResponseSchema(BaseModel):
    region: str
    events: List[CloudTrailEventSchema]


# VPC Schemas
class VpcSchema(BaseModel):
    vpc_id: Optional[str] = None
    cidr_block: Optional[str] = None
    is_default: bool = False
    state: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class SubnetSchema(BaseModel):
    subnet_id: Optional[str] = None
    vpc_id: Optional[str] = None
    cidr_block: Optional[str] = None
    availability_zone: Optional[str] = None
    available_ip_address_count: Optional[int] = None
    map_public_ip_on_launch: bool = False
    tags: Dict[str, str] = Field(default_factory=dict)


class RouteSchema(BaseModel):
    destination_cidr_block: Optional[str] = None
    gateway_id: Optional[str] = None
    instance_id: Optional[str] = None
    nat_gateway_id: Optional[str] = None
    state: Optional[str] = None


class RouteTableAssociationSchema(BaseModel):
    subnet_id: Optional[str] = None
    main: bool = False


class RouteTableSchema(BaseModel):
    route_table_id: Optional[str] = None
    vpc_id: Optional[str] = None
    routes: List[RouteSchema] = Field(default_factory=list)
    associations: List[RouteTableAssociationSchema] = Field(default_factory=list)


class InternetGatewayAttachmentSchema(BaseModel):
    vpc_id: Optional[str] = None
    state: Optional[str] = None


class InternetGatewaySchema(BaseModel):
    internet_gateway_id: Optional[str] = None
    attachments: List[InternetGatewayAttachmentSchema] = Field(default_factory=list)


class NatGatewaySchema(BaseModel):
    nat_gateway_id: Optional[str] = None
    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None
    state: Optional[str] = None


class VpcInfrastructureSchema(BaseModel):
    vpcs: List[VpcSchema] = Field(default_factory=list)
    subnets: List[SubnetSchema] = Field(default_factory=list)
    route_tables: List[RouteTableSchema] = Field(default_factory=list)
    internet_gateways: List[InternetGatewaySchema] = Field(default_factory=list)
    nat_gateways: List[NatGatewaySchema] = Field(default_factory=list)


class VpcResponseSchema(BaseModel):
    region: str
    vpc: VpcInfrastructureSchema


# Security Groups Schemas
class SecurityRuleSchema(BaseModel):
    protocol: Optional[str] = None
    from_port: Optional[int] = None
    to_port: Optional[int] = None
    sources: List[str] = Field(default_factory=list)


class SecurityGroupSchema(BaseModel):
    group_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    vpc_id: Optional[str] = None
    inbound_rules: List[SecurityRuleSchema] = Field(default_factory=list)
    outbound_rules: List[SecurityRuleSchema] = Field(default_factory=list)


class SecurityGroupResponseSchema(BaseModel):
    region: str
    security_groups: List[SecurityGroupSchema]


# Load Balancer Schemas
class TargetHealthSchema(BaseModel):
    target_id: Optional[str] = None
    port: Optional[int] = None
    health_state: Optional[str] = None
    reason: Optional[str] = None
    description: Optional[str] = None


class TargetGroupSchema(BaseModel):
    target_group_arn: Optional[str] = None
    target_group_name: Optional[str] = None
    protocol: Optional[str] = None
    port: Optional[int] = None
    vpc_id: Optional[str] = None
    health_check_protocol: Optional[str] = None
    health_check_port: Optional[str] = None
    health_check_path: Optional[str] = None
    target_health: List[TargetHealthSchema] = Field(default_factory=list)


class LoadBalancerSchema(BaseModel):
    load_balancer_arn: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    state: Optional[str] = None
    dns_name: Optional[str] = None
    vpc_id: Optional[str] = None
    availability_zones: List[str] = Field(default_factory=list)
    target_groups: List[TargetGroupSchema] = Field(default_factory=list)


class LoadBalancerResponseSchema(BaseModel):
    region: str
    load_balancers: List[LoadBalancerSchema]


# Host-Level / SSM Telemetry Schemas
class WindowsServiceSchema(BaseModel):
    name: str
    display_name: Optional[str] = None
    status: str
    start_type: Optional[str] = None


class ListeningPortSchema(BaseModel):
    port: Optional[int] = None
    local_address: Optional[str] = None
    state: Optional[str] = "Listen"
    owning_process: Optional[int] = None


class HostSystemInfoSchema(BaseModel):
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    last_boot_time: Optional[str] = None
    total_memory_kb: Optional[int] = None
    free_memory_kb: Optional[int] = None


class HostTelemetrySchema(BaseModel):
    instance_id: str
    platform: Optional[str] = "windows"
    collection_method: Optional[str] = "ssm_run_command"
    services: List[WindowsServiceSchema] = Field(default_factory=list)
    listening_ports: List[ListeningPortSchema] = Field(default_factory=list)
    system_info: HostSystemInfoSchema = Field(default_factory=HostSystemInfoSchema)
    error: Optional[str] = None


class HostTelemetryResponseSchema(BaseModel):
    region: str
    host_telemetry: List[HostTelemetrySchema] = Field(default_factory=list)


# Aggregate Infrastructure Data Schema
class InfrastructureDataResponseSchema(BaseModel):
    region: str
    timestamp: str
    ec2: List[EC2InstanceSchema]
    cloudwatch: List[CloudWatchMetricSchema]
    cloudtrail: List[CloudTrailEventSchema]
    vpc: VpcInfrastructureSchema
    security_groups: List[SecurityGroupSchema]
    load_balancers: List[LoadBalancerSchema]
    host_telemetry: List[HostTelemetrySchema] = Field(default_factory=list)

