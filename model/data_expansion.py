import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from model.config import PROJECT_ROOT, RANDOM_SEED
from model.prompts import CLOUDOPS_SYSTEM_PROMPT

PROMPT_VARIATIONS = [
    "Analyze this AWS infrastructure incident and determine the probable root cause.",
    "Why is the application or service degraded or unreachable based on this cloud telemetry?",
    "Identify the likely root cause and recommend advisory corrective steps.",
    "Review this cloud incident telemetry and extract factual evidence and probable root cause.",
    "What is causing this infrastructure failure?",
    "Analyze the provided cloud signals and provide a safe advisory diagnosis.",
    "Diagnose the underlying operational issue from the provided AWS cloud signals.",
    "Evaluate the observed cloud telemetry and CloudTrail logs to identify the root cause.",
    "Investigate the reported cloud anomaly and determine the primary probable cause.",
    "Analyze the given infrastructure metrics and events to form an evidence-based diagnosis.",
]

ALL_SERVICES = [
    "EC2", "EBS", "VPC", "Subnets", "Route Tables", "Internet Gateway", "NAT Gateway",
    "Security Groups", "Network ACLs", "ALB", "Target Groups", "CloudWatch", "CloudTrail",
    "IAM", "S3", "RDS", "Lambda", "ECS", "EKS", "Auto Scaling", "Route 53/DNS",
    "TLS/SSL", "Application Failures", "Resource Exhaustion", "Multi-Service Incidents"
]

SCENARIO_TYPES = [
    "SINGLE_CAUSE",
    "MULTI_SIGNAL",
    "COMPETING_CAUSE",
    "INSUFFICIENT_EVIDENCE",
    "MISLEADING_SYMPTOM",
    "CLOUDTRAIL_CORRELATION",
    "CONFIGURATION_MISMATCH",
    "APPLICATION_VS_INFRASTRUCTURE",
]


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates word-token Jaccard similarity between two text strings."""
    words1 = set(re.findall(r"\w+", text1.lower()))
    words2 = set(re.findall(r"\w+", text2.lower()))
    if not words1 or not words2:
        return 0.0
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / union if union > 0 else 0.0


class CloudOpsScenarioGenerator:
    """
    Enhanced synthetic scenario generator for CloudOps LLM instruction tuning.
    Features:
    - 25 AWS service categories with rich sub-template pools
    - 8 distinct scenario types (including low-confidence uncertainty cases)
    - Canonical semantic signature deduplication
    - On-the-fly Jaccard similarity near-duplicate rejection
    """

    def __init__(self, seed: int = RANDOM_SEED, similarity_threshold: float = 0.75):
        self.seed = seed
        self.similarity_threshold = similarity_threshold
        random.seed(seed)

    def generate_scenarios(self, count_per_category: int = 6) -> List[Dict[str, Any]]:
        """Generates synthetic instruction-tuning examples covering all 25 categories and 8 scenario types."""
        examples: List[Dict[str, Any]] = []
        seen_signatures: Set[Tuple[str, str, str]] = set()
        seen_texts: List[str] = []

        scenario_type_counter = 0

        for category in ALL_SERVICES:
            generated_for_cat = 0
            retries = 0

            while generated_for_cat < count_per_category and retries < 50:
                retries += 1
                scenario_type = SCENARIO_TYPES[scenario_type_counter % len(SCENARIO_TYPES)]
                scenario_type_counter += 1

                ex, signature = self._create_category_scenario(category, generated_for_cat, scenario_type)

                if not ex or not signature:
                    continue

                # 1. Semantic signature check
                if signature in seen_signatures:
                    continue

                # 2. On-the-fly Jaccard text similarity check
                full_text = ex["instruction"] + " " + ex["input"]
                is_near_dup = False
                for prev_text in seen_texts:
                    if calculate_jaccard_similarity(full_text, prev_text) >= self.similarity_threshold:
                        is_near_dup = True
                        break

                if is_near_dup:
                    continue

                # Accept scenario
                seen_signatures.add(signature)
                seen_texts.append(full_text)
                examples.append(ex)
                generated_for_cat += 1

        return examples

    def _create_category_scenario(self, category: str, idx: int, scenario_type: str) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, str]]]:
        inst_id = f"i-0gen{idx:03d}{random.randint(100,999)}"
        vpc_id = f"vpc-0gen{idx:03d}{random.randint(10,99)}"
        sg_id = f"sg-0gen{idx:03d}{random.randint(10,99)}"
        subnet_id = f"subnet-0gen{idx:03d}{random.randint(10,99)}"
        instruction = random.choice(PROMPT_VARIATIONS)

        # Handle INSUFFICIENT_EVIDENCE scenario type (confidence <= 0.50)
        if scenario_type == "INSUFFICIENT_EVIDENCE":
            input_text = f"User reports application performance degradation on {category} resource in VPC {vpc_id}. Current CPU utilization is 35%. No memory metrics, disk I/O logs, or recent CloudTrail events are available."
            output_obj = {
                "problem": f"{category} service performance degradation",
                "probable_root_cause": "Available telemetry is ambiguous and insufficient to conclusively prove root cause",
                "evidence": [
                    f"Resource telemetry for {category} shows normal CPU at 35%",
                    "Memory, disk I/O, and application log metrics are uncollected"
                ],
                "impact": "End-user latency experienced, but underlying bottleneck remains unverified",
                "recommendation": f"Enable CloudWatch detailed monitoring and application APM tracing for {category} before selecting remediation",
                "confidence": round(random.uniform(0.35, 0.48), 2)
            }
            sig = (category, "INSUFFICIENT_EVIDENCE", f"sub_{idx}")
            return self._build_example(instruction, input_text, output_obj, category, scenario_type), sig

        # Category sub-scenarios
        if category == "EC2":
            variant = idx % 3
            if variant == 0:
                input_text = f"EC2 instance {inst_id} state is stopped. Console indicates instance was stopped via StopInstances API. Web app is completely offline."
                output_obj = {
                    "problem": f"EC2 instance {inst_id} is in stopped state",
                    "probable_root_cause": f"EC2 instance {inst_id} is stopped, halting process execution and network connectivity",
                    "evidence": [f"EC2 instance {inst_id} state is reported as stopped", "StopInstances API call recorded"],
                    "impact": "Hosted web application is completely offline and unreachable",
                    "recommendation": f"Start instance {inst_id} and verify service process startup",
                    "confidence": 0.96
                }
                mech = "INSTANCE_STOPPED"
            elif variant == 1:
                cpu = random.randint(89, 99)
                input_text = f"EC2 instance {inst_id} CPU utilization is sustained at {cpu}% for 45 minutes. HTTP requests to app latency is 6000ms."
                output_obj = {
                    "problem": f"Severe CPU exhaustion on instance {inst_id}",
                    "probable_root_cause": f"High computational workload on {inst_id} causing sustained {cpu}% CPU saturation",
                    "evidence": [f"EC2 instance {inst_id} CPU utilization is {cpu}%", "HTTP latency is 6000ms"],
                    "impact": "Application latency is severely degraded",
                    "recommendation": f"Inspect high CPU processes on instance {inst_id} or scale out instance capacity",
                    "confidence": 0.93
                }
                mech = "CPU_SATURATION"
            else:
                input_text = f"EC2 status check StatusCheckFailed_System triggered for {inst_id}. Underlying hypervisor host experienced hardware failure."
                output_obj = {
                    "problem": f"EC2 system status check failure on {inst_id}",
                    "probable_root_cause": f"Underlying AWS physical host hardware degradation affecting instance {inst_id}",
                    "evidence": [f"StatusCheckFailed_System is ALARM for {inst_id}", "Hypervisor host hardware fault reported"],
                    "impact": "Instance is unresponsive due to host hardware failure",
                    "recommendation": f"Stop and start instance {inst_id} to migrate it to a healthy physical host",
                    "confidence": 0.95
                }
                mech = "SYSTEM_STATUS_CHECK"

        elif category == "EBS":
            variant = idx % 2
            vol_id = f"vol-0ebs{idx:03d}"
            if variant == 0:
                input_text = f"EBS volume {vol_id} attached to {inst_id} shows VolumeQueueLength > 60 and VolumeThroughputPercentage < 15%. I/O write operations log timeout errors."
                output_obj = {
                    "problem": f"EBS volume I/O bottleneck on volume {vol_id}",
                    "probable_root_cause": f"EBS volume {vol_id} exhausted its IOPS burst credit balance",
                    "evidence": [f"EBS volume {vol_id} VolumeQueueLength > 60", "I/O write operation timeouts logged"],
                    "impact": "Disk write operations are heavily delayed",
                    "recommendation": f"Upgrade volume {vol_id} to gp3 or io2 with provisioned IOPS",
                    "confidence": 0.92
                }
                mech = "IOPS_EXHAUSTION"
            else:
                input_text = f"EC2 instance {inst_id} fails to boot. System log indicates volume {vol_id} attached to /dev/sda1 is in error state."
                output_obj = {
                    "problem": f"Root EBS volume error on {inst_id}",
                    "probable_root_cause": f"Root EBS volume {vol_id} entered degraded error state, preventing OS kernel boot",
                    "evidence": [f"Root volume {vol_id} state is error", f"Instance {inst_id} system log reports boot device failure"],
                    "impact": "EC2 instance cannot complete boot sequence",
                    "recommendation": f"Restore volume {vol_id} from recent EBS snapshot and reattach as root device /dev/sda1",
                    "confidence": 0.94
                }
                mech = "BOOT_VOLUME_ERROR"

        elif category == "VPC":
            input_text = f"Instances in VPC {vpc_id} cannot resolve internal DNS hostnames. VPC attribute enableDnsHostnames is set to false."
            output_obj = {
                "problem": "VPC internal DNS hostname resolution failure",
                "probable_root_cause": f"VPC {vpc_id} attribute enableDnsHostnames is set to false",
                "evidence": [f"VPC {vpc_id} attribute enableDnsHostnames is false", "Internal DNS queries fail"],
                "impact": "Private DNS hostname resolution fails within VPC",
                "recommendation": f"Enable enableDnsHostnames and enableDnsSupport on VPC {vpc_id}",
                "confidence": 0.96
            }
            mech = "DNS_HOSTNAMES_DISABLED"

        elif category == "Subnets":
            input_text = f"Lambda function associated with Subnet {subnet_id} failed execution with ENILimitReached. Subnet AvailableIpAddressCount is 0."
            output_obj = {
                "problem": f"Subnet IP address pool exhaustion in {subnet_id}",
                "probable_root_cause": f"Subnet {subnet_id} has 0 available IP addresses, preventing Elastic Network Interface (ENI) allocation",
                "evidence": [f"Subnet {subnet_id} AvailableIpAddressCount is 0", "ENILimitReached error logged"],
                "impact": "New network interfaces and Lambda instances cannot be provisioned in subnet",
                "recommendation": f"Migrate workloads to a subnet with available IP CIDR space",
                "confidence": 0.95
            }
            mech = "IP_EXHAUSTION"

        elif category == "Route Tables":
            rtb_id = f"rtb-0route{idx:03d}"
            input_text = f"Subnet {subnet_id} associated with Route Table {rtb_id} cannot reach external APIs. Default route 0.0.0.0/0 points to blackholed NAT Gateway nat-0123."
            output_obj = {
                "problem": "Subnet outbound internet routing failure",
                "probable_root_cause": f"Route Table {rtb_id} default route 0.0.0.0/0 targets a deleted NAT Gateway nat-0123 in blackhole state",
                "evidence": [f"Route Table {rtb_id} target 0.0.0.0/0 is blackholed", "Outbound external API calls fail"],
                "impact": "Outbound internet traffic from subnet is dropped",
                "recommendation": f"Update Route Table {rtb_id} default route to an active NAT Gateway",
                "confidence": 0.96
            }
            mech = "BLACKHOLE_ROUTE"

        elif category == "Internet Gateway":
            igw_id = f"igw-0net{idx:03d}"
            input_text = f"Public Subnet {subnet_id} hosts instance {inst_id} with Elastic IP. Inbound web traffic times out. Internet Gateway {igw_id} is detached from VPC {vpc_id}."
            output_obj = {
                "problem": "Public internet ingress/egress failure for VPC",
                "probable_root_cause": f"Internet Gateway {igw_id} is detached from VPC {vpc_id}",
                "evidence": [f"Internet Gateway {igw_id} is detached from VPC {vpc_id}", "Inbound traffic to Elastic IP times out"],
                "impact": "VPC public subnets are isolated from the internet",
                "recommendation": f"Attach Internet Gateway {igw_id} to VPC {vpc_id}",
                "confidence": 0.97
            }
            mech = "IGW_DETACHED"

        elif category == "NAT Gateway":
            nat_id = f"nat-0gateway{idx:03d}"
            input_text = f"Private subnet instances cannot download updates. NAT Gateway {nat_id} status is failed due to Elastic IP allocation failure."
            output_obj = {
                "problem": "NAT Gateway operational failure",
                "probable_root_cause": f"NAT Gateway {nat_id} is in failed state due to Elastic IP allocation error",
                "evidence": [f"NAT Gateway {nat_id} status is failed", "Outbound connections time out from private subnet"],
                "impact": "Private subnets lose outbound internet access",
                "recommendation": f"Re-create NAT Gateway {nat_id} with allocated Elastic IP and update route tables",
                "confidence": 0.94
            }
            mech = "NAT_FAILED"

        elif category == "Security Groups":
            port = 3306 if idx % 2 == 0 else 443
            protocol = "MySQL" if port == 3306 else "HTTPS"
            input_text = f"App server logged connection timeout connecting to database at 10.0.2.45:{port}. Security Group {sg_id} inbound rules permit TCP {port} only from 10.0.1.0/24. App server is in 10.0.3.0/24."
            output_obj = {
                "problem": f"{protocol} connection timeout on port {port}",
                "probable_root_cause": f"Security Group {sg_id} inbound rules do not permit TCP port {port} from app subnet 10.0.3.0/24",
                "evidence": [f"App server connection timeout to port {port}", f"Security Group {sg_id} restricts port {port} to 10.0.1.0/24"],
                "impact": f"App server cannot connect to {protocol} service",
                "recommendation": f"Authorize TCP port {port} in Security Group {sg_id} for app server subnet 10.0.3.0/24",
                "confidence": 0.95
            }
            mech = f"SG_BLOCKED_PORT_{port}"

        elif category == "Network ACLs":
            nacl_id = f"nacl-0acl{idx:03d}"
            input_text = f"Security Group permits TCP port 80. However, HTTP requests to {inst_id} time out. Network ACL {nacl_id} Rule 100 explicitly DENIES TCP port 80 inbound."
            output_obj = {
                "problem": "HTTP traffic blocked at subnet border",
                "probable_root_cause": f"Network ACL {nacl_id} Rule 100 explicitly DENIES inbound TCP port 80 traffic",
                "evidence": ["Security Group permits port 80", f"Network ACL {nacl_id} Rule 100 DENIES TCP port 80"],
                "impact": "HTTP traffic is rejected at subnet boundary",
                "recommendation": f"Modify Network ACL {nacl_id} Rule 100 to ALLOW TCP port 80",
                "confidence": 0.96
            }
            mech = "NACL_DENY"

        elif category == "ALB":
            alb_id = f"alb-prod{idx:03d}"
            input_text = f"Clients accessing https://api.cloudops.internal receive SSL_ERROR_SYSCALL. ALB {alb_id} listener on port 443 uses an ACM SSL certificate that expired 2 days ago."
            output_obj = {
                "problem": "ALB HTTPS SSL handshake failure",
                "probable_root_cause": f"ACM SSL certificate attached to ALB {alb_id} HTTPS listener on port 443 has expired",
                "evidence": ["SSL handshake fails with SSL_ERROR_SYSCALL", f"ACM certificate on ALB {alb_id} port 443 is expired"],
                "impact": "HTTPS clients cannot establish TLS connections to ALB",
                "recommendation": f"Renew ACM SSL certificate and update HTTPS listener on ALB {alb_id}",
                "confidence": 0.96
            }
            mech = "ALB_CERT_EXPIRED"

        elif category == "Target Groups":
            tg_id = f"tg-app{idx:03d}"
            input_text = f"ALB returns 502 Bad Gateway. Target Group {tg_id} health check port is configured as 8080, but application process on {inst_id} listens on port 8000."
            output_obj = {
                "problem": "ALB 502 Bad Gateway due to health check port mismatch",
                "probable_root_cause": f"Target Group {tg_id} health check port (8080) does not match application listening port (8000) on {inst_id}",
                "evidence": ["ALB returns 502 Bad Gateway", f"Target Group {tg_id} checks port 8080 while app runs on 8000"],
                "impact": "ALB marks all targets unhealthy and cannot route requests",
                "recommendation": f"Update Target Group {tg_id} health check port to 8000",
                "confidence": 0.95
            }
            mech = "TG_PORT_MISMATCH"

        elif category == "CloudWatch":
            alarm_name = f"alarm-latency-{idx:03d}"
            input_text = f"CloudWatch Alarm {alarm_name} status is ALARM. Metric TargetResponseTime for ALB averaged 8.5s over 3 evaluation periods. EC2 CPU is low (15%)."
            output_obj = {
                "problem": "High ALB target response time alarm",
                "probable_root_cause": "Backend database queries or external microservices are delaying HTTP response completion",
                "evidence": [f"CloudWatch Alarm {alarm_name} metric TargetResponseTime is 8.5s", "EC2 instance CPU is low at 15%"],
                "impact": "End-user web request latencies are elevated",
                "recommendation": "Inspect application database query execution times and APM traces",
                "confidence": 0.89
            }
            mech = "CW_LATENCY_ALARM"

        elif category == "CloudTrail":
            input_text = f"CloudTrail audit log records RevokeSecurityGroupIngress on sg-prod-web by dev-intern 10 minutes ago, removing TCP 443 ingress. Web traffic timed out shortly after."
            output_obj = {
                "problem": "Security Group ingress rule removal causing outage",
                "probable_root_cause": "CloudTrail record confirms RevokeSecurityGroupIngress removed TCP 443 ingress from sg-prod-web",
                "evidence": ["CloudTrail logged RevokeSecurityGroupIngress on sg-prod-web", "Connection timeouts began immediately after event"],
                "impact": "HTTPS clients are blocked from reaching web servers",
                "recommendation": "Re-authorize TCP 443 ingress on sg-prod-web in Security Group settings",
                "confidence": 0.97
            }
            mech = "CLOUDTRAIL_REVOKE_SG"

        elif category == "IAM":
            input_text = f"S3 upload script on instance {inst_id} logs AccessDenied: Access Denied. Attached IAM Role Role-EC2-App policy statement lacks s3:PutObject on bucket prod-data-bucket."
            output_obj = {
                "problem": "IAM permission denied for S3 PutObject",
                "probable_root_cause": "IAM Role Role-EC2-App lacks s3:PutObject action permission for bucket prod-data-bucket",
                "evidence": ["Application logs AccessDenied on S3 upload", "IAM Role policy statement omits s3:PutObject permission"],
                "impact": "Automated S3 data pipeline upload fails",
                "recommendation": "Grant s3:PutObject permission on arn:aws:s3:::prod-data-bucket/* to Role-EC2-App",
                "confidence": 0.95
            }
            mech = "IAM_DENIED_S3"

        elif category == "S3":
            bucket = f"s3-data-{idx:03d}"
            input_text = f"HTTP 403 Forbidden returned accessing objects in S3 bucket {bucket}. Bucket policy contains statement Effect: Deny, Action: s3:GetObject, StringNotEquals aws:PrincipalOrgID."
            output_obj = {
                "problem": "S3 bucket object 403 Access Denied",
                "probable_root_cause": f"S3 bucket {bucket} policy denies s3:GetObject for requests originating outside AWS Organization ID",
                "evidence": ["Client receives HTTP 403 Forbidden", f"Bucket policy on {bucket} includes explicit Deny for non-Org principals"],
                "impact": "External client requests cannot download S3 bucket objects",
                "recommendation": f"Adjust bucket policy on {bucket} or use CloudFront OAI/OAC",
                "confidence": 0.94
            }
            mech = "S3_POLICY_DENY"

        elif category == "RDS":
            db_id = f"rds-db-{idx:03d}"
            input_text = f"RDS DB Instance {db_id} status is storage-full. FreeStorageSpace metric dropped to 0 MB. Application logs FATAL disk full error."
            output_obj = {
                "problem": f"RDS DB Instance {db_id} storage exhaustion",
                "probable_root_cause": f"RDS DB instance {db_id} has 0 MB FreeStorageSpace available",
                "evidence": [f"RDS DB instance {db_id} status is storage-full", "FreeStorageSpace metric is 0 MB"],
                "impact": "Database rejects write operations and aborts transactions",
                "recommendation": f"Increase RDS allocated storage on {db_id} and enable storage autoscaling",
                "confidence": 0.97
            }
            mech = "RDS_STORAGE_FULL"

        elif category == "Lambda":
            func_name = f"lambda-func-{idx:03d}"
            input_text = f"AWS Lambda function {func_name} execution failed with Task timed out after 3.00 seconds. Function timeout setting is 3s. HTTP call to external API takes 4.5s."
            output_obj = {
                "problem": f"Lambda function {func_name} execution timeout",
                "probable_root_cause": f"Lambda function {func_name} timeout (3s) is shorter than external API call duration (4.5s)",
                "evidence": ["Lambda execution failed with Task timed out after 3.00s", "External HTTP API call duration is 4.5s"],
                "impact": "Lambda invocations fail to complete and return error responses",
                "recommendation": f"Increase Lambda function {func_name} timeout setting to 15 seconds",
                "confidence": 0.95
            }
            mech = "LAMBDA_TIMEOUT"

        elif category == "ECS":
            cluster = f"ecs-cluster-{idx:03d}"
            input_text = f"ECS task in cluster {cluster} continuously transitions PENDING to STOPPED with error Essential container in task exited with code 1. Logs: Cannot connect to Redis host redis.internal:6379."
            output_obj = {
                "problem": f"ECS task container crash loop in cluster {cluster}",
                "probable_root_cause": "Essential container process failed startup due to unhandled exception connecting to Redis endpoint",
                "evidence": ["ECS task stopped with Essential container exited (exit code 1)", "Container logs: Cannot connect to Redis host redis.internal:6379"],
                "impact": "ECS service cannot maintain desired running task count",
                "recommendation": "Verify Redis endpoint hostname resolution and network accessibility",
                "confidence": 0.93
            }
            mech = "ECS_CONTAINER_CRASH"

        elif category == "EKS":
            pod_name = f"pod-web-{idx:03d}"
            input_text = f"Kubernetes pod {pod_name} in EKS cluster shows status OOMKilled (exit code 137). Container spec memory limit is 256Mi. Peak memory was 258Mi."
            output_obj = {
                "problem": f"EKS pod {pod_name} memory OOMKilled",
                "probable_root_cause": f"Pod container memory consumption exceeded configured spec limit of 256Mi, triggering Linux kernel OOM killer",
                "evidence": [f"Pod {pod_name} status is OOMKilled (exit code 137)", "Container memory limit 256Mi, peak memory 258Mi"],
                "impact": "Pod container restarts repeatedly, disrupting web traffic",
                "recommendation": f"Increase container memory limit in pod deployment manifest to 512Mi",
                "confidence": 0.96
            }
            mech = "EKS_POD_OOM"

        elif category == "Auto Scaling":
            asg_name = f"asg-web-{idx:03d}"
            input_text = f"Auto Scaling Group {asg_name} failed to launch instances. Activity status message: ValidationException: Requested instance type t3.micro is not supported in az-1."
            output_obj = {
                "problem": f"Auto Scaling Group {asg_name} instance launch failure",
                "probable_root_cause": f"Launch template for ASG {asg_name} specifies instance type t3.micro which is unavailable in AZ az-1",
                "evidence": [f"ASG {asg_name} activity status reports ValidationException for t3.micro in az-1", "Desired capacity > actual instance count"],
                "impact": "ASG cannot scale out capacity during high traffic demand",
                "recommendation": f"Update ASG launch template to include supported instance types in target subnets",
                "confidence": 0.95
            }
            mech = "ASG_LAUNCH_FAILED"

        elif category == "Route 53/DNS":
            domain = f"app{idx}.cloudops.demo"
            input_text = f"DNS resolution for {domain} returns SERVFAIL. Route 53 ALIAS record points to alb-123.Target ALB alb-123 was deleted 1 day ago."
            output_obj = {
                "problem": f"Route 53 DNS resolution failure for {domain}",
                "probable_root_cause": f"Route 53 ALIAS record for {domain} points to a deleted Application Load Balancer alb-123",
                "evidence": [f"DNS query for {domain} returns SERVFAIL", "Route 53 ALIAS target alb-123 does not exist"],
                "impact": "Clients cannot resolve domain IP addresses",
                "recommendation": f"Update Route 53 ALIAS record for {domain} to target an active ALB",
                "confidence": 0.96
            }
            mech = "DNS_ALIAS_DELETED_TARGET"

        elif category == "TLS/SSL":
            input_text = f"HTTPS client connection to https://app{idx}.internal fails with err_cert_common_name_invalid. Server TLS certificate CN is api.internal, requested domain is app{idx}.internal."
            output_obj = {
                "problem": "TLS/SSL certificate domain name mismatch",
                "probable_root_cause": f"Server TLS certificate Subject Common Name (CN=api.internal) does not match requested hostname app{idx}.internal",
                "evidence": ["Client logs err_cert_common_name_invalid", "Server cert CN is api.internal, requested is app{idx}.internal"],
                "impact": "Browsers and API clients reject the TLS connection",
                "recommendation": f"Re-issue TLS certificate including app{idx}.internal in Subject Alternative Names",
                "confidence": 0.94
            }
            mech = "TLS_CN_MISMATCH"

        elif category == "Application Failures":
            input_text = f"HTTP requests to EC2 instance {inst_id} return 500 Internal Server Error. Nginx proxy is running on port 80. Python Gunicorn service on port 5000 is stopped."
            output_obj = {
                "problem": "Nginx 500 Internal Server Error / Bad Gateway",
                "probable_root_cause": f"Upstream application process Gunicorn on port 5000 is stopped, causing Nginx reverse proxy failure",
                "evidence": ["Nginx returns HTTP 500/502 to clients", "Gunicorn process on port 5000 is stopped"],
                "impact": "Web application endpoints return 500 errors to clients",
                "recommendation": f"Restart Gunicorn application service on instance {inst_id}",
                "confidence": 0.95
            }
            mech = "APP_PROCESS_STOPPED"

        elif category == "Resource Exhaustion":
            input_text = f"EC2 instance {inst_id} memory utilization is 98.5%. Linux dmesg logs show Out of memory: Kill process 4512 (java). Java web service process was killed."
            output_obj = {
                "problem": f"Host OS Out-Of-Memory (OOM) process termination on {inst_id}",
                "probable_root_cause": f"Physical RAM exhaustion (98.5%) triggered Linux kernel OOM killer to terminate Java application process (PID 4512)",
                "evidence": [f"EC2 instance {inst_id} RAM utilization is 98.5%", "Kernel dmesg logs Out of memory: Kill process 4512 (java)"],
                "impact": "Java web service is killed, taking application offline",
                "recommendation": "Configure Java JVM max heap size (-Xmx) below instance RAM capacity",
                "confidence": 0.97
            }
            mech = "HOST_OOM_KILL"

        else:  # Multi-Service Incidents
            input_text = f"EKS pod web-app fails database connection. Subnet {subnet_id} Route Table lacks NAT Gateway route. Security Group sg-db blocks port 5432. CloudTrail shows SG rule revoked 1 hour ago."
            output_obj = {
                "problem": "Multi-dependency database connection failure for EKS workload",
                "probable_root_cause": "Database connection is blocked by both Security Group sg-db ingress revocation and missing subnet NAT Gateway route",
                "evidence": ["Security Group sg-db lacks TCP 5432 ingress permission", "Route Table lacks 0.0.0.0/0 route to NAT Gateway", "CloudTrail logs RevokeSecurityGroupIngress on sg-db"],
                "impact": "EKS pods cannot establish database sessions",
                "recommendation": "Restore TCP 5432 ingress rule on sg-db and configure default route to NAT Gateway in subnet route table",
                "confidence": 0.92
            }
            mech = "MULTI_SERVICE_SG_AND_ROUTE"

        signature = (category, mech, scenario_type)
        return self._build_example(instruction, input_text, output_obj, category, scenario_type), signature

    def _build_example(self, instruction: str, input_text: str, output_obj: Dict[str, Any], category: str, scenario_type: str) -> Dict[str, Any]:
        return {
            "instruction": instruction,
            "input": input_text,
            "output": json.dumps(output_obj),
            "_metadata": {
                "category": category,
                "scenario_type": scenario_type,
                "source": "enhanced_synthetic_generator_v3",
                "license": "Internal / Proprietary",
                "provenance": f"CloudOps Generator ({scenario_type})"
            }
        }


class ExternalDatasetImporter:
    """
    Importer & normalizer for external public postmortem/RCA incident datasets.
    Tracks source, license, category, and provenance for every imported record.
    """

    def import_from_jsonl(
        self,
        filepath: Path,
        source_name: str,
        license_name: str,
        category_mapping: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Imports and normalizes external incident examples from a JSONL file."""
        imported_examples = []
        if not filepath.exists():
            return imported_examples

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    raw_item = json.loads(line)
                    normalized = self.normalize_item(raw_item, source_name, license_name, category_mapping)
                    if normalized:
                        imported_examples.append(normalized)
                except Exception:
                    continue

        return imported_examples

    def normalize_item(
        self,
        raw_item: Dict[str, Any],
        source_name: str,
        license_name: str,
        category_mapping: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Normalizes external raw incident item into standard CloudOps schema."""
        instruction = raw_item.get("instruction") or raw_item.get("prompt") or "Analyze this infrastructure incident."
        input_text = raw_item.get("input") or raw_item.get("context") or raw_item.get("telemetry")
        output_raw = raw_item.get("output") or raw_item.get("diagnosis") or raw_item.get("response")

        if not input_text or not output_raw:
            return None

        if isinstance(output_raw, str):
            try:
                output_obj = json.loads(output_raw)
            except Exception:
                output_obj = {
                    "problem": "Reported incident",
                    "probable_root_cause": output_raw[:200],
                    "evidence": ["External incident report context provided"],
                    "impact": "Operational service degradation",
                    "recommendation": "Review postmortem findings and apply preventive controls",
                    "confidence": 0.85
                }
        elif isinstance(output_raw, dict):
            output_obj = output_raw
        else:
            return None

        category = raw_item.get("category", "General")
        if category_mapping and category in category_mapping:
            category = category_mapping[category]

        return {
            "instruction": instruction.strip(),
            "input": input_text.strip(),
            "output": json.dumps(output_obj),
            "_metadata": {
                "category": category,
                "scenario_type": raw_item.get("scenario_type", "EXTERNAL_RCA"),
                "source": source_name,
                "license": license_name,
                "provenance": raw_item.get("provenance", f"Imported from {source_name}")
            }
        }
