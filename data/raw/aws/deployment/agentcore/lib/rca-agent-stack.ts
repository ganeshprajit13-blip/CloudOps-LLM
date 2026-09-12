import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudtrail from 'aws-cdk-lib/aws-cloudtrail';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { Construct } from 'constructs';
import * as path from 'path';

export interface RcaAgentStackProps extends cdk.NestedStackProps {
  agentName: string;
  memoryRetentionDays: number;
  description?: string;
  knowledgeBaseId?: string;
  /** Cognito User Pool construct for Cognito authorizer. */
  cognitoUserPool: cognito.IUserPool;
  /** Cognito User Pool Client construct for Cognito authorizer. */
  cognitoUserPoolClient: cognito.IUserPoolClient;
  /** Athena database name (from AthenaLogSearchStack). */
  athenaDatabase?: string;
  /** Athena table name (from AthenaLogSearchStack). */
  athenaTable?: string;
  /** Athena results S3 bucket name (from AthenaLogSearchStack). */
  athenaResultsBucket?: string;
}

/**
 * AgentCore execution role with necessary permissions for the RCA agent.
 */
class RcaAgentCoreRole extends iam.Role {
  constructor(scope: Construct, id: string, props: {
    agentName: string;
    knowledgeBaseId?: string;
  }) {
    const stack = cdk.Stack.of(scope);

    super(scope, id, {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
        new iam.AccountPrincipal(stack.account),
      ),
      description: `Execution role for ${props.agentName} RCA Agent on AgentCore and local dev`,
      inlinePolicies: {
        AgentCorePolicy: new iam.PolicyDocument({
          statements: [
            // ECR access for container images
            new iam.PolicyStatement({
              sid: 'ECRImageAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'ecr:BatchGetImage',
                'ecr:GetDownloadUrlForLayer',
                'ecr:BatchCheckLayerAvailability',
              ],
              resources: [`arn:aws:ecr:${stack.region}:${stack.account}:repository/*`],
            }),
            new iam.PolicyStatement({
              sid: 'ECRTokenAccess',
              effect: iam.Effect.ALLOW,
              actions: ['ecr:GetAuthorizationToken'],
              resources: ['*'],
            }),
            // CloudWatch Logs
            new iam.PolicyStatement({
              sid: 'CloudWatchLogsGroupAccess',
              effect: iam.Effect.ALLOW,
              actions: ['logs:DescribeLogStreams', 'logs:CreateLogGroup'],
              resources: [
                `arn:aws:logs:${stack.region}:${stack.account}:log-group:/aws/bedrock-agentcore/runtimes/*`,
              ],
            }),
            new iam.PolicyStatement({
              sid: 'CloudWatchLogsDescribeGroups',
              effect: iam.Effect.ALLOW,
              actions: ['logs:DescribeLogGroups'],
              resources: [`arn:aws:logs:${stack.region}:${stack.account}:log-group:*`],
            }),
            new iam.PolicyStatement({
              sid: 'CloudWatchLogsStreamAccess',
              effect: iam.Effect.ALLOW,
              actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
              resources: [
                `arn:aws:logs:${stack.region}:${stack.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`,
              ],
            }),
            // X-Ray tracing
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
                'xray:GetSamplingRules',
                'xray:GetSamplingTargets',
              ],
              resources: ['*'],
            }),
            // CloudWatch metrics
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['cloudwatch:PutMetricData'],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cloudwatch:namespace': 'bedrock-agentcore',
                },
              },
            }),
            // AgentCore Identity
            new iam.PolicyStatement({
              sid: 'GetAgentAccessToken',
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:GetWorkloadAccessToken',
                'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
                'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
              ],
              resources: [
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default/workload-identity/*`,
              ],
            }),
            // Bedrock model invocation
            new iam.PolicyStatement({
              sid: 'BedrockModelInvocation',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
              resources: [
                'arn:aws:bedrock:*::foundation-model/*',
                `arn:aws:bedrock:${stack.region}:${stack.account}:*`,
              ],
            }),
            // Bedrock Knowledge Base access
            new iam.PolicyStatement({
              sid: 'BedrockKBAccess',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock:Retrieve'],
              resources: props.knowledgeBaseId
                ? [`arn:aws:bedrock:${stack.region}:${stack.account}:knowledge-base/${props.knowledgeBaseId}`]
                : [`arn:aws:bedrock:${stack.region}:${stack.account}:knowledge-base/*`],
            }),
            // CloudWatch Logs search (for log investigation)
            new iam.PolicyStatement({
              sid: 'CloudWatchLogsSearch',
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:FilterLogEvents',
                'logs:GetLogEvents',
                'logs:DescribeLogGroups',
                'logs:DescribeLogStreams',
              ],
              resources: [`arn:aws:logs:${stack.region}:${stack.account}:log-group:*`],
            }),
            // Athena access (for S3 log search)
            new iam.PolicyStatement({
              sid: 'AthenaAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'athena:StartQueryExecution',
                'athena:GetQueryExecution',
                'athena:GetQueryResults',
                'athena:StopQueryExecution',
              ],
              resources: [`arn:aws:athena:${stack.region}:${stack.account}:workgroup/*`],
            }),
            // S3 access for Athena results and log data
            new iam.PolicyStatement({
              sid: 'S3Access',
              effect: iam.Effect.ALLOW,
              actions: [
                's3:GetObject',
                's3:PutObject',
                's3:ListBucket',
                's3:GetBucketLocation',
              ],
              resources: [
                `arn:aws:s3:::rca-agent-*`,
                `arn:aws:s3:::rca-agent-*/*`,
              ],
            }),
            // Glue for Athena table metadata
            new iam.PolicyStatement({
              sid: 'GlueAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'glue:GetTable',
                'glue:GetTables',
                'glue:GetDatabase',
                'glue:GetDatabases',
                'glue:GetPartitions',
              ],
              resources: [
                `arn:aws:glue:${stack.region}:${stack.account}:catalog`,
                `arn:aws:glue:${stack.region}:${stack.account}:database/*`,
                `arn:aws:glue:${stack.region}:${stack.account}:table/*`,
              ],
            }),
          ],
        }),
      },
    });
  }
}

/**
 * Backend resources for the RCA Deep Research Agent.
 *
 * Deployed as a nested stack inside RcaMainStack.
 */
export class RcaAgentStack extends cdk.NestedStack {
  public readonly runtimeArn: string = '';
  public readonly runtimeId: string = '';
  public readonly memoryArn: string = '';
  public readonly repositoryUri: string;
  public readonly checkpointTableName: string;
  public readonly configTableName: string;
  public readonly logGroupName: string;
  public readonly executionRoleArn: string;
  public readonly dashboardName: string;

  constructor(scope: Construct, id: string, props: RcaAgentStackProps) {
    super(scope, id, props);

    const {
      agentName, memoryRetentionDays, description, knowledgeBaseId,
      cognitoUserPool, cognitoUserPoolClient,
      athenaDatabase, athenaTable, athenaResultsBucket,
    } = props;
    const parentStack = cdk.Stack.of(this);
    const dockerfilePath = 'patterns/rca-deep-research/Dockerfile';

    // ==========================================================================
    // ECR Repository for Agent Container
    // ==========================================================================
    const repository = new ecr.Repository(this, 'AgentRepository', {
      repositoryName: `${agentName}-runtime`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      emptyOnDelete: true,
      imageScanOnPush: true,
      encryption: ecr.RepositoryEncryption.AES_256,
      imageTagMutability: ecr.TagMutability.IMMUTABLE,
      lifecycleRules: [
        {
          maxImageCount: 10,
          description: 'Keep only 10 most recent images',
        },
      ],
    });
    this.repositoryUri = repository.repositoryUri;

    // ==========================================================================
    // AgentCore Execution Role
    // ==========================================================================
    const executionRole = new RcaAgentCoreRole(this, 'AgentCoreRole', {
      agentName,
      knowledgeBaseId,
    });
    this.executionRoleArn = executionRole.roleArn;

    // ==========================================================================
    // CloudWatch Log Group
    // ==========================================================================
    const logGroup = new logs.LogGroup(this, 'AgentLogGroup', {
      logGroupName: `/aws/agentcore/${agentName}`,
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    this.logGroupName = logGroup.logGroupName;

    // ==========================================================================
    // DynamoDB Table for LangGraph Checkpoint Persistence
    // ==========================================================================
    const checkpointTable = new dynamodb.Table(this, 'CheckpointTable', {
      tableName: `${agentName}-checkpoints-v2`,
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: 'expiry',
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });
    checkpointTable.grantReadWriteData(executionRole);
    this.checkpointTableName = checkpointTable.tableName;

    // ==========================================================================
    // DynamoDB Table for Agent Configuration (hot-reloadable via UI)
    // ==========================================================================
    const configTable = new dynamodb.Table(this, 'ConfigTable', {
      tableName: `${agentName}-config`,
      partitionKey: { name: 'AgentName', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'CreatedAt', type: dynamodb.AttributeType.NUMBER },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });
    configTable.grantReadWriteData(executionRole);
    this.configTableName = configTable.tableName;

    // ==========================================================================
    // CloudTrail — DynamoDB Data Plane Event Logging (optional)
    // Not available in all regions. Enable with -c enableCloudTrail=true
    // ==========================================================================
    const enableCloudTrail = this.node.tryGetContext('enableCloudTrail') === true ||
                             this.node.tryGetContext('enableCloudTrail') === 'true';

    if (enableCloudTrail) {
      const trailAccessLogBucket = new s3.Bucket(this, 'CloudTrailAccessLogBucket', {
        enforceSSL: true,
        encryption: s3.BucketEncryption.S3_MANAGED,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
        lifecycleRules: [{ expiration: cdk.Duration.days(90) }],
      });

      const trailBucket = new s3.Bucket(this, 'CloudTrailBucket', {
        enforceSSL: true,
        encryption: s3.BucketEncryption.S3_MANAGED,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
        lifecycleRules: [{ expiration: cdk.Duration.days(90) }],
        serverAccessLogsBucket: trailAccessLogBucket,
        serverAccessLogsPrefix: 'cloudtrail-logs/',
      });

      const trail = new cloudtrail.Trail(this, 'DynamoDBDataTrail', {
        bucket: trailBucket,
        trailName: `${agentName}-dynamodb-data-events`,
        isMultiRegionTrail: false,
        includeGlobalServiceEvents: false,
        enableFileValidation: true,
      });

      const cfnTrail = trail.node.defaultChild as cdk.CfnResource;
      cfnTrail.addPropertyOverride('EventSelectors', [{
        DataResources: [{
          Type: 'AWS::DynamoDB::Table',
          Values: [checkpointTable.tableArn, configTable.tableArn],
        }],
        ReadWriteType: 'All',
      }]);
    }

    // ==========================================================================
    // AgentCore Resources (always deployed)
    // ==========================================================================
    const agentRuntimeArtifact = agentcore.AgentRuntimeArtifact.fromAsset(
      path.resolve(__dirname, '..', '..', '..'),
      {
        platform: ecr_assets.Platform.LINUX_ARM64,
        file: dockerfilePath,
      }
    );

    // AgentCore Memory
    const memory = new cdk.CfnResource(this, 'AgentMemory', {
      type: 'AWS::BedrockAgentCore::Memory',
      properties: {
        Name: `${agentName.replace(/-/g, '_')}_memory`,
        EventExpiryDuration: memoryRetentionDays,
        Description: `Conversation memory for ${agentName} RCA agent`,
        MemoryStrategies: [],
        MemoryExecutionRoleArn: executionRole.roleArn,
        Tags: {
          Name: `${agentName}_Memory`,
          Project: 'rca-deep-research',
          ManagedBy: 'CDK',
        },
      },
    });
    const memoryId = memory.getAtt('MemoryId').toString();
    this.memoryArn = memory.getAtt('MemoryArn').toString();

    executionRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'MemoryResourceAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock-agentcore:CreateEvent',
          'bedrock-agentcore:GetEvent',
          'bedrock-agentcore:ListEvents',
          'bedrock-agentcore:RetrieveMemoryRecords',
        ],
        resources: [this.memoryArn],
      })
    );

    // Runtime environment variables
    const envVars: { [key: string]: string } = {
      AWS_REGION: parentStack.region,
      AWS_DEFAULT_REGION: parentStack.region,
      MEMORY_ID: memoryId,
      RCA_AGENT_MODE: 'production',
      LOG_LEVEL: 'INFO',
      RUNTIME_MODE: 'agentcore',
      CHECKPOINT_BACKEND: 'dynamodb',
      CHECKPOINT_TABLE_NAME: checkpointTable.tableName,
      AGENT_CONFIG_TABLE: configTable.tableName,
      AGENT_NAME: agentName,
      OTEL_ENABLED: 'true',
      OTEL_SERVICE_NAME: agentName,
      OTEL_PROPAGATORS: 'xray',
      OTEL_PYTHON_ID_GENERATOR: 'xray',
    };

    if (knowledgeBaseId) {
      envVars['BEDROCK_KB_ID'] = knowledgeBaseId;
    }

    // Athena log search config (wired from AthenaLogSearchStack)
    if (athenaDatabase && athenaTable && athenaResultsBucket) {
      envVars['LOG_SEARCH_BACKEND'] = 'athena';
      envVars['ATHENA_DATABASE'] = athenaDatabase;
      envVars['ATHENA_TABLE'] = athenaTable;
      envVars['ATHENA_OUTPUT_LOCATION'] = `s3://${athenaResultsBucket}/`;
    }

    // Cognito auth (always deployed)
    envVars['COGNITO_USER_POOL_ID'] = cognitoUserPool.userPoolId;
    envVars['COGNITO_APP_CLIENT_ID'] = cognitoUserPoolClient.userPoolClientId;

    // AgentCore Runtime with Cognito auth
    const runtime = new agentcore.Runtime(this, 'Runtime', {
      runtimeName: `${agentName.replace(/-/g, '_')}_runtime`,
      agentRuntimeArtifact: agentRuntimeArtifact,
      executionRole: executionRole,
      protocolConfiguration: agentcore.ProtocolType.HTTP,
      environmentVariables: envVars,
      description: description || 'Deep Research RCA Agent for incident investigation',
      requestHeaderConfiguration: {
        allowlistedHeaders: ['Authorization'],
      },
      authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingCognito(
        cognitoUserPool,
        [cognitoUserPoolClient],
      ),
    });

    this.runtimeArn = runtime.agentRuntimeArn;
    this.runtimeId = runtime.agentRuntimeId;

    new ssm.StringParameter(this, 'RuntimeArnParam', {
      parameterName: `/${agentName}/runtime-arn`,
      stringValue: runtime.agentRuntimeArn,
      description: 'ARN of the AgentCore Runtime',
    });

    // ==========================================================================
    // CloudWatch Dashboard
    // ==========================================================================
    this.dashboardName = `${agentName}-dashboard`;

    const dashboard = new cloudwatch.Dashboard(this, 'AgentDashboard', {
      dashboardName: this.dashboardName,
    });

    dashboard.addWidgets(
      new cloudwatch.TextWidget({
        markdown: `# ${agentName} - Deep Research RCA Agent\n\nMonitoring dashboard for agent performance and usage.`,
        width: 24,
        height: 2,
      })
    );

    dashboard.addWidgets(
      new cloudwatch.LogQueryWidget({
        title: 'Recent Agent Activity',
        logGroupNames: [logGroup.logGroupName],
        queryLines: [
          'fields @timestamp, @message',
          'sort @timestamp desc',
          'limit 50',
        ],
        width: 24,
        height: 8,
      })
    );
  }
}
