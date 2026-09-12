from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SignalSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalSchema(BaseModel):
    type: str = Field(..., description="Unique signal type identifier, e.g., port_not_allowed")
    severity: SignalSeverity = Field(..., description="Observed signal severity level")
    resource_id: str = Field(..., description="Affected AWS resource ID or ARN")
    description: str = Field(..., description="Factual description of the observed signal")
    value: Optional[Any] = Field(None, description="Observed metric value or state indicator")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional signal context")


class BlockedPortInfoSchema(BaseModel):
    port: int
    security_group_id: str


class ContextSummarySchema(BaseModel):
    total_instances: int = 0
    running_instances: int = 0
    high_cpu_instances: int = 0
    unhealthy_targets: int = 0
    recent_changes: int = 0
    blocked_ports: List[BlockedPortInfoSchema] = Field(default_factory=list)


class NormalizedEC2Schema(BaseModel):
    instance_id: str
    state: str
    instance_type: Optional[str] = None
    private_ip: Optional[str] = None
    public_ip: Optional[str] = None
    availability_zone: Optional[str] = None
    subnet_id: Optional[str] = None
    vpc_id: Optional[str] = None
    security_group_ids: List[str] = Field(default_factory=list)
    tags: Dict[str, str] = Field(default_factory=dict)


class NormalizedVpcInfoSchema(BaseModel):
    vpc_id: str
    cidr: Optional[str] = None
    state: Optional[str] = None


class NormalizedSubnetInfoSchema(BaseModel):
    subnet_id: str
    vpc_id: str
    cidr: Optional[str] = None
    availability_zone: Optional[str] = None


class NormalizedRouteSchema(BaseModel):
    destination: Optional[str] = None
    target: Optional[str] = None
    state: Optional[str] = None


class NormalizedRouteTableSchema(BaseModel):
    route_table_id: str
    vpc_id: str
    routes: List[NormalizedRouteSchema] = Field(default_factory=list)


class NormalizedVPCInfrastructureSchema(BaseModel):
    vpcs: List[NormalizedVpcInfoSchema] = Field(default_factory=list)
    subnets: List[NormalizedSubnetInfoSchema] = Field(default_factory=list)
    route_tables: List[NormalizedRouteTableSchema] = Field(default_factory=list)
    internet_gateways: List[str] = Field(default_factory=list)
    nat_gateways: List[str] = Field(default_factory=list)


class NormalizedRuleSchema(BaseModel):
    protocol: Optional[str] = None
    from_port: Optional[int] = None
    to_port: Optional[int] = None
    sources: List[str] = Field(default_factory=list)


class NormalizedSGSchema(BaseModel):
    group_id: str
    name: Optional[str] = None
    vpc_id: Optional[str] = None
    inbound_rules: List[NormalizedRuleSchema] = Field(default_factory=list)


class UnhealthyTargetSchema(BaseModel):
    target_id: str
    reason: Optional[str] = None
    description: Optional[str] = None


class NormalizedTargetGroupSchema(BaseModel):
    name: str
    port: Optional[int] = None
    protocol: Optional[str] = None
    health_check_path: Optional[str] = None
    unhealthy_targets: List[UnhealthyTargetSchema] = Field(default_factory=list)


class NormalizedALBSchema(BaseModel):
    name: str
    type: Optional[str] = None
    state: Optional[str] = None
    dns_name: Optional[str] = None
    vpc_id: Optional[str] = None
    target_groups: List[NormalizedTargetGroupSchema] = Field(default_factory=list)


class NormalizedServiceSchema(BaseModel):
    name: str
    display_name: Optional[str] = None
    status: str
    start_type: Optional[str] = None


class NormalizedListeningPortSchema(BaseModel):
    port: Optional[int] = None
    local_address: Optional[str] = None
    state: Optional[str] = "Listen"
    owning_process: Optional[int] = None


class NormalizedHostTelemetrySchema(BaseModel):
    instance_id: str
    platform: Optional[str] = "windows"
    collection_method: Optional[str] = "ssm_run_command"
    services: List[NormalizedServiceSchema] = Field(default_factory=list)
    listening_ports: List[NormalizedListeningPortSchema] = Field(default_factory=list)
    win32_service: List[Dict[str, Any]] = Field(default_factory=list)
    process_status: List[Dict[str, Any]] = Field(default_factory=list)
    system_info: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ResourcesContainerSchema(BaseModel):
    ec2: List[NormalizedEC2Schema] = Field(default_factory=list)
    vpc: NormalizedVPCInfrastructureSchema = Field(default_factory=NormalizedVPCInfrastructureSchema)
    security_groups: List[NormalizedSGSchema] = Field(default_factory=list)
    load_balancers: List[NormalizedALBSchema] = Field(default_factory=list)
    host_telemetry: List[NormalizedHostTelemetrySchema] = Field(default_factory=list)



class NormalizedMetricSchema(BaseModel):
    metric_name: str
    resource_id: str
    timestamp: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None


class NormalizedEventSchema(BaseModel):
    event_time: Optional[str] = None
    event_name: str
    event_source: Optional[str] = None
    principal: Optional[str] = None
    region: Optional[str] = None
    resource: Optional[str] = None


class NormalizedCloudContextSchema(BaseModel):
    timestamp: str
    region: str
    summary: ContextSummarySchema
    resources: ResourcesContainerSchema
    metrics: List[NormalizedMetricSchema] = Field(default_factory=list)
    cloudtrail_events: List[NormalizedEventSchema] = Field(default_factory=list)
    signals: List[SignalSchema] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
