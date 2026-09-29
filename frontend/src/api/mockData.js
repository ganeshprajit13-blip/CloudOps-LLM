// Comprehensive Mock Data for CloudOps LLM

export const mockDashboardData = {
  health: {
    overallHealth: '98.4%',
    activeIncidentsCount: 3,
    awsResourcesCount: 48,
    criticalAlertsCount: 2,
    status: 'Warning',
  },
  overview: {
    ec2: {
      total: 18,
      running: 14,
      stopped: 3,
      terminated: 1,
      health: 'Warning',
      avgCpuUtilization: 42.5,
      cpuTimeline: [
        { time: '04:00', cpu: 28 },
        { time: '05:00', cpu: 32 },
        { time: '06:00', cpu: 45 },
        { time: '07:00', cpu: 68 },
        { time: '08:00', cpu: 89 },
        { time: '09:00', cpu: 94 },
        { time: '10:00', cpu: 42 },
      ]
    },
    cloudWatch: {
      activeAlarms: 4,
      errorRate: '1.8%',
      requestCount: '1.42M',
      cpuMetrics: 42.5,
      memoryMetrics: 67.2,
      metricsTimeline: [
        { time: '04:00', requests: 12000, errors: 45, latency: 120 },
        { time: '05:00', requests: 18000, errors: 60, latency: 135 },
        { time: '06:00', requests: 25000, errors: 120, latency: 180 },
        { time: '07:00', requests: 42000, errors: 450, latency: 420 },
        { time: '08:00', requests: 68000, errors: 890, latency: 850 },
        { time: '09:00', requests: 55000, errors: 310, latency: 260 },
        { time: '10:00', requests: 38000, errors: 80, latency: 140 },
      ]
    },
    loadBalancer: {
      healthyTargets: 14,
      unhealthyTargets: 2,
      requestCount: '1.42M',
      http4xx: 2450,
      http5xx: 382,
      status: 'Warning',
      httpTimeline: [
        { time: '04:00', http2xx: 11800, http4xx: 150, http5xx: 12 },
        { time: '05:00', http2xx: 17700, http4xx: 210, http5xx: 18 },
        { time: '06:00', http2xx: 24500, http4xx: 380, http5xx: 45 },
        { time: '07:00', http2xx: 40500, http4xx: 890, http5xx: 180 },
        { time: '08:00', http2xx: 66000, http4xx: 1200, http5xx: 310 },
        { time: '09:00', http2xx: 54000, http4xx: 450, http5xx: 65 },
        { time: '10:00', http2xx: 37500, http4xx: 280, http5xx: 24 },
      ]
    },
    vpcNetwork: {
      vpcs: 3,
      subnets: 12,
      securityGroups: 16,
      networkStatus: 'Healthy',
      trafficInboundGB: 184.5,
      trafficOutboundGB: 342.1
    }
  }
};

export const mockIncidents = [
  {
    id: 'INC-9042',
    title: 'Website Unavailable / HTTPS Port 443 Inaccessible',
    severity: 'Critical',
    service: 'EC2 / Load Balancer',
    status: 'Investigating',
    detectedAt: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    confidence: 92,
    probableCause: 'AWS Security Group rule blocking inbound HTTPS traffic on port 443.',
    summary: 'Primary web service `prod-alb-ingress` target group standard health checks returning HTTP 502 connection refusal due to restrictive security group rules.',
    evidence: [
      { label: 'EC2 instance status', value: 'Running', status: 'pass' },
      { label: 'CPU utilization', value: 'Normal (34%)', status: 'pass' },
      { label: 'Application health', value: 'Healthy (Localhost 8080)', status: 'pass' },
      { label: 'Port 443', value: 'Blocked / Connection Timeout', status: 'fail' },
      { label: 'Security Group sg-0a9b8c', value: 'No inbound HTTPS rule for 0.0.0.0/0', status: 'fail' }
    ],
    recommendedAction: 'Review and update the inbound Security Group rule for TCP port 443 on sg-0a9b8c to allow traffic from ALB security group or 0.0.0.0/0.'
  },
  {
    id: 'INC-8815',
    title: 'High Latency Spikes on API Microservice',
    severity: 'High',
    service: 'CloudWatch / EC2',
    status: 'Identified',
    detectedAt: new Date(Date.now() - 110 * 60 * 1000).toISOString(),
    confidence: 88,
    probableCause: 't3.xlarge CPU credit exhaustion causing CPU throttling.',
    summary: 'Average response latency increased from 140ms to 2400ms following high traffic burst.',
    evidence: [
      { label: 'CPUCreditBalance metric', value: '0 Credits', status: 'fail' },
      { label: 'CPUSurgeCreditBalance', value: 'Depleted', status: 'fail' },
      { label: 'Memory usage', value: '62%', status: 'pass' },
      { label: 'Database connection pool', value: 'Healthy', status: 'pass' }
    ],
    recommendedAction: 'Enable Unlimited Mode for T3 instances or resize instance family to c6i.xlarge for consistent compute throughput.'
  },
  {
    id: 'INC-8430',
    title: 'RDS Postgres Connection Pool Timeout',
    severity: 'Medium',
    service: 'RDS / VPC',
    status: 'Investigating',
    detectedAt: new Date(Date.now() - 240 * 60 * 1000).toISOString(),
    confidence: 85,
    probableCause: 'Maximum connection limit (max_connections=100) reached due to unclosed DB client sockets.',
    summary: 'Backend Lambda workers throwing DB connection acquisition timeout error.',
    evidence: [
      { label: 'Database CPU', value: '45%', status: 'pass' },
      { label: 'Database Storage free space', value: '180 GB', status: 'pass' },
      { label: 'Active Connections', value: '100 / 100 max', status: 'fail' },
      { label: 'DB Subnet NACL', value: 'Allow All', status: 'pass' }
    ],
    recommendedAction: 'Deploy AWS RDS Proxy to manage connection pooling and increase max_connections parameter in DB Parameter Group.'
  },
  {
    id: 'INC-7912',
    title: 'S3 Asset Sync Permission Denied',
    severity: 'Low',
    service: 'S3 / IAM',
    status: 'Resolved',
    detectedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    confidence: 96,
    probableCause: 'IAM Role `EC2-App-Role` missing `s3:PutObject` permission on bucket `cloudops-static-assets`.',
    summary: 'Build deployment script failed to upload static bundle artifacts.',
    evidence: [
      { label: 'Bucket existence', value: 'Verified', status: 'pass' },
      { label: 'Bucket policy', value: 'Enforces SSL', status: 'pass' },
      { label: 'IAM Policy Action', value: 's3:GetObject only', status: 'fail' }
    ],
    recommendedAction: 'Attach `s3:PutObject` permission policy statement to role `EC2-App-Role`.'
  }
];

export const mockTroubleshootingResponses = {
  default: {
    problem: 'Website or service accessibility failure',
    probableRootCause: 'AWS Security Group rule blocking inbound HTTPS traffic on port 443.',
    confidence: 92,
    evidence: [
      { label: 'EC2 instance status', value: 'Running (i-03f9e8a71b2)', status: 'pass' },
      { label: 'CPU utilization', value: 'Normal (28%)', status: 'pass' },
      { label: 'Application health check', value: 'Healthy on 127.0.0.1:8000', status: 'pass' },
      { label: 'Port 443 HTTPS traffic', value: 'Blocked / Connection Refused', status: 'fail' },
      { label: 'Security Group sg-0a9b8c rule', value: 'Missing inbound rule for 443', status: 'fail' }
    ],
    recommendedAction: 'Review and add inbound rule for TCP port 443 in Security Group `sg-0a9b8c` allowing source `0.0.0.0/0` or your Load Balancer SG.',
    impact: 'Users trying to reach https://app.example.com experience browser connection timeout errors.',
    retrievedKnowledge: [
      { title: 'AWS EC2 Security Group Troubleshooting', category: 'AWS Documentation', relevance: '96%', snippet: 'When EC2 instances are healthy locally but unreachable publicly, verify security group ingress rules on port 443/80.' },
      { title: 'ALB Target Group Unhealthy Checklist', category: 'Runbook', relevance: '91%', snippet: 'Ensure security group associated with EC2 instance allows ingress traffic from the ALB security group.' },
      { title: 'VPC NACL vs Security Group Diagnostics', category: 'Architecture Guide', relevance: '85%', snippet: 'Security Groups are stateful; if inbound port 443 is not explicitly permitted, responses will be dropped.' }
    ]
  },
  cpu: {
    problem: 'High CPU utilization spike across EC2 instances',
    probableRootCause: 'Unoptimized worker process loop consuming 100% CPU thread on `i-09f12d8a`.',
    confidence: 89,
    evidence: [
      { label: 'EC2 instance status', value: 'Running', status: 'pass' },
      { label: 'CPU utilization metric', value: '98.6% sustained for 25 minutes', status: 'fail' },
      { label: 'Memory consumption', value: '4.2 GB / 16 GB', status: 'pass' },
      { label: 'Disk I/O Wait', value: 'Low (0.2%)', status: 'pass' }
    ],
    recommendedAction: 'Restart worker process `cloudops-worker.service` and inspect Python thread dump for infinite loops.',
    impact: 'API response times delayed by > 3000ms; auto-scaling trigger imminent.',
    retrievedKnowledge: [
      { title: 'Debugging High CPU Spikes on EC2', category: 'Troubleshooting Guide', relevance: '94%', snippet: 'Use `htop` or `py-spy` to inspect stack traces of high CPU consuming processes on Linux instances.' }
    ]
  }
};

export const mockLogs = [
  { id: 'log-101', timestamp: new Date(Date.now() - 2 * 60 * 1000).toISOString(), service: 'EC2', level: 'ERROR', message: 'Connection timeout while connecting to port 443 on host 10.0.1.42', rawJson: '{"event":"connection_refused","port":443,"host":"10.0.1.42","service":"EC2","vpc_id":"vpc-01a2b3"}' },
  { id: 'log-102', timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(), service: 'ALB', level: 'WARNING', message: 'Target group `tg-frontend` registered target `i-03f9e8a71b2` status changed to UNHEALTHY', rawJson: '{"event":"target_unhealthy","target_id":"i-03f9e8a71b2","tg":"tg-frontend","reason":"Target.ResponseCodeMismatch"}' },
  { id: 'log-103', timestamp: new Date(Date.now() - 8 * 60 * 1000).toISOString(), service: 'CloudWatch', level: 'ERROR', message: 'Alarm `HighHTTP5xxErrorRate` state updated to ALARM. Threshold exceeded: > 5.0%', rawJson: '{"alarm_name":"HighHTTP5xxErrorRate","threshold":5.0,"current":8.4,"service":"CloudWatch"}' },
  { id: 'log-104', timestamp: new Date(Date.now() - 12 * 60 * 1000).toISOString(), service: 'RDS', level: 'ERROR', message: 'FATAL: remaining connection slots are reserved for non-replication superuser connections', rawJson: '{"event":"db_connection_exhaustion","db_instance":"cloudops-db-prod","max_connections":100}' },
  { id: 'log-105', timestamp: new Date(Date.now() - 18 * 60 * 1000).toISOString(), service: 'EC2', level: 'INFO', message: 'Auto-scaling group `asg-web-frontend` launched new instance `i-09f12d8a` in us-east-1a', rawJson: '{"event":"instance_launch","instance_id":"i-09f12d8a","az":"us-east-1a"}' },
  { id: 'log-106', timestamp: new Date(Date.now() - 24 * 60 * 1000).toISOString(), service: 'VPC', level: 'WARNING', message: 'VPC Flow Log rejected 142 packets on ENI `eni-0c91823` from 198.51.100.4 to port 443', rawJson: '{"event":"flow_log_reject","eni":"eni-0c91823","src":"198.51.100.4","dst_port":443}' },
  { id: 'log-107', timestamp: new Date(Date.now() - 35 * 60 * 1000).toISOString(), service: 'Lambda', level: 'INFO', message: 'Function `cloudops-log-ingest` executed successfully in 142ms. Billed duration: 150ms', rawJson: '{"function":"cloudops-log-ingest","duration_ms":142,"billed_ms":150,"memory_mb":256}' },
  { id: 'log-108', timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(), service: 'CloudWatch', level: 'INFO', message: 'Metric stream `cloudops-metrics-firehose` delivered 14,200 records to S3 bucket', rawJson: '{"records":14200,"stream":"cloudops-metrics-firehose"}' }
];

export const mockResources = {
  ec2: [
    { instanceId: 'i-03f9e8a71b2', name: 'prod-web-server-01', status: 'Running', instanceType: 't3.medium', cpu: '28%', az: 'us-east-1a', launchTime: '2026-08-15 08:30' },
    { instanceId: 'i-09f12d8a4e1', name: 'prod-web-server-02', status: 'Running', instanceType: 't3.medium', cpu: '34%', az: 'us-east-1b', launchTime: '2026-08-15 08:32' },
    { instanceId: 'i-0b7c4d1f2a3', name: 'staging-api-server', status: 'Stopped', instanceType: 't3.small', cpu: '0%', az: 'us-east-1a', launchTime: '2026-09-01 12:00' },
    { instanceId: 'i-0d5e6f7a8b9', name: 'worker-node-01', status: 'Running', instanceType: 'c6i.xlarge', cpu: '88%', az: 'us-east-1c', launchTime: '2026-08-20 14:15' }
  ],
  vpc: [
    { vpcId: 'vpc-01a2b3c4d5', name: 'cloudops-prod-vpc', cidrBlock: '10.0.0.0/16', subnetsCount: 6, state: 'Available', defaultVpc: false },
    { vpcId: 'vpc-09f8e7d6c5', name: 'cloudops-staging-vpc', cidrBlock: '172.31.0.0/16', subnetsCount: 3, state: 'Available', defaultVpc: true }
  ],
  securityGroups: [
    { groupId: 'sg-0a9b8c7d6e', name: 'web-public-sg', vpcId: 'vpc-01a2b3c4d5', inboundRules: 3, outboundRules: 1, description: 'Allows port 80 & 443 traffic from ALB' },
    { groupId: 'sg-0f1e2d3c4b', name: 'internal-app-sg', vpcId: 'vpc-01a2b3c4d5', inboundRules: 2, outboundRules: 1, description: 'Internal app microservice communications' },
    { groupId: 'sg-05a4b3c2d1', name: 'db-postgres-sg', vpcId: 'vpc-01a2b3c4d5', inboundRules: 1, outboundRules: 0, description: 'Restricted 5432 ingress from app SG' }
  ],
  loadBalancers: [
    { albName: 'prod-alb-ingress', dnsName: 'prod-alb-ingress-1849204.us-east-1.elb.amazonaws.com', type: 'application', state: 'active', targetGroupsCount: 2, scheme: 'internet-facing' },
    { albName: 'internal-microservices-alb', dnsName: 'internal-alb-90184.us-east-1.elb.amazonaws.com', type: 'application', state: 'active', targetGroupsCount: 4, scheme: 'internal' }
  ],
  cloudWatch: [
    { alarmName: 'HighHTTP5xxErrorRate', metric: 'HTTPCode_Target_5XX_Count', threshold: '> 5.0', state: 'ALARM', updatedAt: '10 mins ago' },
    { alarmName: 'EC2HighCPUUtilization', metric: 'CPUUtilization', threshold: '> 85%', state: 'ALARM', updatedAt: '2 hours ago' },
    { alarmName: 'RDSFreeStorageSpace', metric: 'FreeStorageSpace', threshold: '< 10 GB', state: 'OK', updatedAt: '1 day ago' }
  ]
};

export const mockAnalysisHistory = [
  {
    id: 'hist-101',
    date: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    problem: 'Website unreachable / HTTPS port 443 connection drop',
    service: 'EC2 / Load Balancer',
    probableCause: 'Security Group sg-0a9b8c rule missing inbound 443 permit',
    confidence: 92,
    status: 'Resolved',
    userFeedback: 'Correct',
    feedbackComment: 'Spot on! The security group rule was deleted during Terraform update.'
  },
  {
    id: 'hist-102',
    date: new Date(Date.now() - 3 * 3600 * 1000).toISOString(),
    problem: 'API Gateway returning 504 Gateway Timeout',
    service: 'CloudWatch / Lambda',
    probableCause: 'Lambda execution timeout set too low (3 seconds) for external API call',
    confidence: 89,
    status: 'Resolved',
    userFeedback: null,
    feedbackComment: ''
  },
  {
    id: 'hist-103',
    date: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
    problem: 'High memory usage alert on worker node 01',
    service: 'EC2 / CloudWatch',
    probableCause: 'Memory leak in node.js background queue consumer worker',
    confidence: 84,
    status: 'Investigating',
    userFeedback: null,
    feedbackComment: ''
  }
];

export const mockKnowledgeBase = [
  {
    id: 'kb-01',
    title: 'AWS Security Group & NACL Troubleshooting Guide',
    category: 'AWS Documentation',
    lastUpdated: '2026-08-30',
    chunksCount: 24,
    status: 'Indexed',
    description: 'Official AWS architecture patterns for diagnosing security group ingress/egress rules and VPC Flow Logs.',
    sampleChunk: 'Security Groups are stateful firewalls. If an inbound connection is allowed on port 443, outbound response traffic is automatically allowed regardless of outbound rules.'
  },
  {
    id: 'kb-02',
    title: 'EC2 Performance & CPU Credit Exhaustion',
    category: 'EC2 Troubleshooting Guide',
    lastUpdated: '2026-09-01',
    chunksCount: 18,
    status: 'Indexed',
    description: 'Guidelines for identifying T2/T3 CPU credit exhaustion, burstable performance thresholds, and CloudWatch metrics.',
    sampleChunk: 'When CPUCreditBalance drops to 0, T3 instances are throttled to baseline CPU performance (20% per core for t3.medium).'
  },
  {
    id: 'kb-03',
    title: 'Application Load Balancer 5xx Error Diagnosis',
    category: 'VPC Networking Guide',
    lastUpdated: '2026-08-25',
    chunksCount: 32,
    status: 'Indexed',
    description: 'Troubleshooting HTTP 502 Bad Gateway and HTTP 504 Gateway Timeout on AWS ALBs.',
    sampleChunk: 'HTTP 502 indicates that the load balancer received an invalid response or connection reset from the target instance on port 80/443.'
  },
  {
    id: 'kb-04',
    title: 'RDS PostgreSQL Connection Pool Runbook',
    category: 'Database Troubleshooting',
    lastUpdated: '2026-09-04',
    chunksCount: 15,
    status: 'Indexed',
    description: 'Best practices for managing max_connections and configuring AWS RDS Proxy for serverless/Lambda callers.',
    sampleChunk: 'Exceeding max_connections will cause client drivers to fail immediately with FATAL: remaining connection slots are reserved.'
  },
  {
    id: 'kb-05',
    title: 'Historical CloudOps Incident Case Studies',
    category: 'Previous Cases',
    lastUpdated: '2026-09-07',
    chunksCount: 42,
    status: 'Active',
    description: 'Aggregated internal resolution post-mortems and root-cause analyses from previous production incidents.',
    sampleChunk: 'Incident post-mortem #204: Inbound Security Group rule dropped during CI/CD terraform apply step.'
  }
];

export const mockBillingData = {
  summary: {
    monthlySpend: 3420.50,
    budgetLimit: 4000.00,
    projectedSpend: 3850.00,
    savingsOpportunitiesCount: 3,
    currency: 'USD',
    period: 'September 2026'
  },
  byService: [
    { name: 'EC2 Instances', cost: 1840.00, percentage: 53.8, color: '#6366f1' },
    { name: 'RDS PostgreSQL', cost: 680.00, percentage: 19.9, color: '#0ea5e9' },
    { name: 'CloudWatch Logs', cost: 420.00, percentage: 12.3, color: '#f59e0b' },
    { name: 'Application Load Balancer', cost: 310.00, percentage: 9.1, color: '#10b981' },
    { name: 'S3 & Data Transfer', cost: 170.50, percentage: 4.9, color: '#ec4899' }
  ],
  dailyCosts: [
    { day: 'Sep 01', cost: 110.20 },
    { day: 'Sep 02', cost: 112.50 },
    { day: 'Sep 03', cost: 108.40 },
    { day: 'Sep 04', cost: 125.80 },
    { day: 'Sep 05', cost: 145.20 },
    { day: 'Sep 06', cost: 118.00 },
    { day: 'Sep 07', cost: 114.30 },
    { day: 'Sep 08', cost: 116.10 }
  ],
  anomalies: [
    {
      id: 'cost-anom-01',
      title: 'T3 CPU Surge Credit burst cost anomaly',
      service: 'EC2',
      impact: '+$34.50 / day',
      severity: 'Medium',
      aiRecommendation: 'Convert T3 instance to Unlimited mode or scale to c6i.xlarge compute instance.'
    },
    {
      id: 'cost-anom-02',
      title: 'Unused Elastic IP Address detected',
      service: 'VPC',
      impact: '+$7.20 / month',
      severity: 'Low',
      aiRecommendation: 'Release unattached Elastic IP eipalloc-09f182.'
    }
  ],
  invoices: [
    { id: 'INV-2026-08', period: 'August 2026', amount: '$3,812.40', status: 'Paid', date: 'Aug 31, 2026' },
    { id: 'INV-2026-07', period: 'July 2026', amount: '$3,640.10', status: 'Paid', date: 'Jul 31, 2026' },
    { id: 'INV-2026-06', period: 'June 2026', amount: '$3,490.80', status: 'Paid', date: 'Jun 30, 2026' }
  ]
};

