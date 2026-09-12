import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3vectors from 'aws-cdk-lib/aws-s3vectors';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cr from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';
import * as path from 'path';

export interface KnowledgeBaseStackProps extends cdk.StackProps {
  agentName: string;
  syncSampleData?: boolean;
}

/**
 * Knowledge Base stack using S3 Vectors.
 *
 * Uses native CloudFormation resources:
 * - AWS::S3Vectors::VectorBucket - Vector storage bucket
 * - AWS::S3Vectors::Index - Vector index
 * - AWS::Bedrock::KnowledgeBase - KB with S3 Vectors backend
 *
 * Cost: Pay-per-query (~90% cheaper than OpenSearch Serverless)
 */
export class KnowledgeBaseStack extends cdk.Stack {
  public readonly bucketName: string;
  public readonly bucketArn: string;
  public readonly knowledgeBaseId: string;
  public readonly dataSourceId: string;

  constructor(scope: Construct, id: string, props: KnowledgeBaseStackProps) {
    super(scope, id, props);

    const { agentName, syncSampleData = false } = props;
    const vectorIndexName = `${agentName}-embeddings`;

    // ==========================================================================
    // Resource Tags for all resources in this stack
    // ==========================================================================
    cdk.Tags.of(this).add('Project', 'rca-deep-research');
    cdk.Tags.of(this).add('Component', 'knowledge-base');
    cdk.Tags.of(this).add('ManagedBy', 'cdk');

    // ==========================================================================
    // S3 Access Logs Bucket (for DSR S3-001 compliance)
    // ==========================================================================
    const accessLogsBucket = new s3.Bucket(this, 'AccessLogsBucket', {
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(90) }],
    });

    // ==========================================================================
    // S3 Bucket for Knowledge Base Source Documents
    // ==========================================================================
    const dataBucket = new s3.Bucket(this, 'KnowledgeBaseBucket', {
      bucketName: `${agentName}-kb-data-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'kb-data-logs/',
      lifecycleRules: [
        {
          // Move to Glacier after 180 days, delete after 365
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(180),
            },
          ],
          expiration: cdk.Duration.days(365),
        },
      ],
    });

    this.bucketName = dataBucket.bucketName;
    this.bucketArn = dataBucket.bucketArn;

    // ==========================================================================
    // S3 Vectors Bucket and Index
    // ==========================================================================

    // Create vector bucket for storing embeddings
    const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
      vectorBucketName: `${agentName}-vectors`,
      encryptionConfiguration: {
        sseType: 'AES256',
      },
    });

    // Create vector index (dimension 1024 for Titan Embed V2)
    // Bedrock KB stores chunk text as AMAZON_BEDROCK_TEXT_CHUNK in metadata.
    // S3 Vectors has a 2048-byte limit on filterable metadata, so the text
    // chunk must be marked non-filterable to avoid ingestion failures.
    const vectorIndex = new s3vectors.CfnIndex(this, 'VectorIndex', {
      vectorBucketName: vectorBucket.vectorBucketName!,
      indexName: vectorIndexName,
      dataType: 'float32',
      dimension: 1024,  // Amazon Titan Embed Text V2
      distanceMetric: 'cosine',
      metadataConfiguration: {
        nonFilterableMetadataKeys: ['AMAZON_BEDROCK_TEXT_CHUNK'],
      },
    });
    vectorIndex.addDependency(vectorBucket);

    // ==========================================================================
    // IAM Role for Bedrock Knowledge Base
    // ==========================================================================
    const kbRole = new iam.Role(this, 'KnowledgeBaseRole', {
      roleName: `${agentName}-kb-role`,
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Role for Bedrock Knowledge Base to access S3 and S3 Vectors',
    });

    // Create managed policy for KB role (ensures proper dependency ordering)
    const kbPolicy = new iam.ManagedPolicy(this, 'KnowledgeBasePolicy', {
      managedPolicyName: `${agentName}-kb-policy`,
      roles: [kbRole],
      statements: [
        // S3 data bucket access
        new iam.PolicyStatement({
          actions: ['s3:GetObject', 's3:ListBucket'],
          resources: [dataBucket.bucketArn, `${dataBucket.bucketArn}/*`],
        }),
        // S3 Vectors access
        new iam.PolicyStatement({
          actions: [
            's3vectors:QueryVectors',
            's3vectors:PutVectors',
            's3vectors:GetVectors',
            's3vectors:DeleteVectors',
            's3vectors:ListVectors',
            's3vectors:GetIndex',
          ],
          resources: [
            vectorBucket.attrVectorBucketArn,
            `${vectorBucket.attrVectorBucketArn}/*`,
            vectorIndex.attrIndexArn,
          ],
        }),
        // Embedding model access
        new iam.PolicyStatement({
          actions: ['bedrock:InvokeModel'],
          resources: [`arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`],
        }),
      ],
    });

    // ==========================================================================
    // Bedrock Knowledge Base with S3 Vectors Storage
    // ==========================================================================
    const knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', {
      name: `${agentName}-knowledge-base`,
      description: 'RCA agent knowledge base with runbooks and past incidents',
      roleArn: kbRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        },
      },
      storageConfiguration: {
        type: 'S3_VECTORS',
        s3VectorsConfiguration: {
          vectorBucketArn: vectorBucket.attrVectorBucketArn,
          indexArn: vectorIndex.attrIndexArn,
        },
      },
    });

    // Ensure dependencies are created before KB
    knowledgeBase.node.addDependency(vectorIndex);
    knowledgeBase.node.addDependency(kbPolicy);

    this.knowledgeBaseId = knowledgeBase.attrKnowledgeBaseId;

    // ==========================================================================
    // Data Source (S3 bucket with documents)
    // ==========================================================================
    const dataSource = new bedrock.CfnDataSource(this, 'S3DataSource', {
      knowledgeBaseId: knowledgeBase.attrKnowledgeBaseId,
      name: `${agentName}-s3-source`,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: dataBucket.bucketArn,
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'NONE',
        },
      },
    });

    this.dataSourceId = dataSource.attrDataSourceId;

    // ==========================================================================
    // Sample Data Deployment (Optional)
    // ==========================================================================
    if (syncSampleData) {
      const deploymentLogGroup = new logs.LogGroup(this, 'DeploymentLogGroup', {
        retention: logs.RetentionDays.ONE_DAY,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      });

      const deployment = new s3deploy.BucketDeployment(this, 'SampleDataDeployment', {
        sources: [
          s3deploy.Source.asset(path.join(__dirname, '../../../scenarios'), {
            exclude: ['**/evidence/**', '**/*.log', '**/ground_truth.yaml'],
          }),
        ],
        destinationBucket: dataBucket,
        destinationKeyPrefix: 'scenarios/',
        prune: false,
        memoryLimit: 512,
        logGroup: deploymentLogGroup,
      });

      const syncTrigger = new cr.AwsCustomResource(this, 'TriggerIngestion', {
        onCreate: {
          service: 'BedrockAgent',
          action: 'startIngestionJob',
          parameters: {
            knowledgeBaseId: knowledgeBase.attrKnowledgeBaseId,
            dataSourceId: dataSource.attrDataSourceId,
          },
          physicalResourceId: cr.PhysicalResourceId.of(`ingestion-${Date.now()}`),
        },
        onUpdate: {
          service: 'BedrockAgent',
          action: 'startIngestionJob',
          parameters: {
            knowledgeBaseId: knowledgeBase.attrKnowledgeBaseId,
            dataSourceId: dataSource.attrDataSourceId,
          },
          physicalResourceId: cr.PhysicalResourceId.of(`ingestion-${Date.now()}`),
        },
        policy: cr.AwsCustomResourcePolicy.fromStatements([
          new iam.PolicyStatement({
            actions: ['bedrock:StartIngestionJob'],
            resources: [`arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/${knowledgeBase.attrKnowledgeBaseId}`],
          }),
        ]),
      });

      syncTrigger.node.addDependency(deployment);
      syncTrigger.node.addDependency(dataSource);
    }

    // ==========================================================================
    // Outputs
    // ==========================================================================
    new cdk.CfnOutput(this, 'DataBucketName', {
      value: dataBucket.bucketName,
      description: 'S3 bucket for knowledge base source documents',
      exportName: `${agentName}-kb-bucket`,
    });

    new cdk.CfnOutput(this, 'VectorBucketArn', {
      value: vectorBucket.attrVectorBucketArn,
      description: 'S3 Vectors bucket ARN',
      exportName: `${agentName}-vector-bucket-arn`,
    });

    new cdk.CfnOutput(this, 'VectorIndexArn', {
      value: vectorIndex.attrIndexArn,
      description: 'S3 Vectors index ARN',
      exportName: `${agentName}-vector-index-arn`,
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: knowledgeBase.attrKnowledgeBaseId,
      description: 'Bedrock Knowledge Base ID',
      exportName: `${agentName}-kb-id`,
    });

    new cdk.CfnOutput(this, 'DataSourceId', {
      value: dataSource.attrDataSourceId,
      exportName: `${agentName}-datasource-id`,
    });

    new cdk.CfnOutput(this, 'Usage', {
      value: `
S3 Vectors Knowledge Base deployed.

For log search, configure CloudWatch Logs:
  export CLOUDWATCH_LOG_GROUP_PREFIX=/rca-agent/scenarios

Environment variables:
  export BEDROCK_KB_ID=${knowledgeBase.attrKnowledgeBaseId}
`.trim(),
    });

    new cdk.CfnOutput(this, 'CostEstimate', {
      value: 'S3 Vectors: Pay-per-query (~90% cheaper than OpenSearch Serverless)',
    });
  }
}
