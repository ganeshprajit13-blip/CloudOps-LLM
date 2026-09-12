import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as glue from 'aws-cdk-lib/aws-glue';
import * as athena from 'aws-cdk-lib/aws-athena';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface AthenaLogSearchStackProps extends cdk.StackProps {
  agentName: string;
}

/**
 * Athena Log Search Stack for RCA Agent.
 *
 * Creates infrastructure for querying logs stored in S3 using Athena:
 * - S3 bucket for log storage (partitioned by date)
 * - S3 bucket for Athena query results
 * - Glue database and table
 * - Athena workgroup
 *
 * Benefits over CloudWatch:
 * - No 14-day timestamp limit
 * - Pay per query (~$5/TB scanned)
 * - SQL-based queries
 * - Works with historical data
 */
export class AthenaLogSearchStack extends cdk.Stack {
  public readonly logBucketName: string;
  public readonly logBucketArn: string;
  public readonly resultsBucketName: string;
  public readonly databaseName: string;
  public readonly tableName: string;
  public readonly workgroupName: string;

  constructor(scope: Construct, id: string, props: AthenaLogSearchStackProps) {
    super(scope, id, props);

    const { agentName } = props;

    // ==========================================================================
    // Resource Tags for all resources in this stack
    // ==========================================================================
    cdk.Tags.of(this).add('Project', 'rca-deep-research');
    cdk.Tags.of(this).add('Component', 'log-search');
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
    // S3 Bucket for Logs
    // ==========================================================================
    const logBucket = new s3.Bucket(this, 'LogBucket', {
      bucketName: `${agentName}-logs-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'log-bucket-logs/',
      lifecycleRules: [
        {
          // Move to Glacier after 90 days, delete after 365
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
          expiration: cdk.Duration.days(365),
        },
      ],
    });

    this.logBucketName = logBucket.bucketName;
    this.logBucketArn = logBucket.bucketArn;

    // ==========================================================================
    // S3 Bucket for Athena Query Results
    // ==========================================================================
    const resultsBucket = new s3.Bucket(this, 'AthenaResultsBucket', {
      bucketName: `${agentName}-athena-results-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'athena-results-logs/',
      lifecycleRules: [
        {
          // Delete query results after 7 days
          expiration: cdk.Duration.days(7),
        },
      ],
    });

    this.resultsBucketName = resultsBucket.bucketName;

    // ==========================================================================
    // Glue Database
    // ==========================================================================
    const database = new glue.CfnDatabase(this, 'LogDatabase', {
      catalogId: this.account,
      databaseInput: {
        name: `${agentName.replace(/-/g, '_')}_logs`,
        description: 'RCA Agent log database for Athena queries',
      },
    });

    this.databaseName = `${agentName.replace(/-/g, '_')}_logs`;

    // ==========================================================================
    // Glue Table (with partition projection for efficient queries)
    // ==========================================================================
    const table = new glue.CfnTable(this, 'LogTable', {
      catalogId: this.account,
      databaseName: this.databaseName,
      tableInput: {
        name: 'logs',
        description: 'RCA Agent logs partitioned by date',
        tableType: 'EXTERNAL_TABLE',
        parameters: {
          'classification': 'json',
          'typeOfData': 'file',
          // Enable partition projection for automatic partition discovery
          'projection.enabled': 'true',
          'projection.year.type': 'integer',
          'projection.year.range': '2020,2030',
          'projection.month.type': 'integer',
          'projection.month.range': '1,12',
          'projection.month.digits': '2',
          'projection.day.type': 'integer',
          'projection.day.range': '1,31',
          'projection.day.digits': '2',
          'storage.location.template': `s3://${logBucket.bucketName}/rca-logs/\${year}/\${month}/\${day}`,
        },
        storageDescriptor: {
          location: `s3://${logBucket.bucketName}/rca-logs/`,
          inputFormat: 'org.apache.hadoop.mapred.TextInputFormat',
          outputFormat: 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
          serdeInfo: {
            serializationLibrary: 'org.openx.data.jsonserde.JsonSerDe',
            parameters: {
              'serialization.format': '1',
              'ignore.malformed.json': 'true',
            },
          },
          columns: [
            { name: 'timestamp', type: 'string' },
            { name: 'level', type: 'string' },
            { name: 'service', type: 'string' },
            { name: 'category', type: 'string' },
            { name: 'message', type: 'string' },
            { name: 'source_file', type: 'string' },
            { name: 'scenario', type: 'string' },
          ],
        },
        partitionKeys: [
          { name: 'year', type: 'string' },
          { name: 'month', type: 'string' },
          { name: 'day', type: 'string' },
        ],
      },
    });

    table.addDependency(database);
    this.tableName = 'logs';

    // ==========================================================================
    // Athena Workgroup
    // ==========================================================================
    const workgroup = new athena.CfnWorkGroup(this, 'AthenaWorkgroup', {
      name: `${agentName}-workgroup`,
      description: 'RCA Agent Athena workgroup',
      state: 'ENABLED',
      workGroupConfiguration: {
        enforceWorkGroupConfiguration: true,
        publishCloudWatchMetricsEnabled: true,
        resultConfiguration: {
          outputLocation: cdk.Fn.sub('s3://${BucketName}/', {
            BucketName: resultsBucket.bucketName,
          }),
          encryptionConfiguration: {
            encryptionOption: 'SSE_S3',
          },
        },
        engineVersion: {
          selectedEngineVersion: 'Athena engine version 3',
        },
        bytesScannedCutoffPerQuery: 10737418240, // 10 GB limit
      },
    });

    this.workgroupName = workgroup.name!;

    // ==========================================================================
    // Outputs
    // ==========================================================================
    new cdk.CfnOutput(this, 'LogBucketName', {
      value: logBucket.bucketName,
      description: 'S3 bucket for storing logs',
      exportName: `${agentName}-log-bucket`,
    });

    new cdk.CfnOutput(this, 'ResultsBucketName', {
      value: resultsBucket.bucketName,
      description: 'S3 bucket for Athena query results',
      exportName: `${agentName}-athena-results-bucket`,
    });

    new cdk.CfnOutput(this, 'AthenaDatabase', {
      value: this.databaseName,
      description: 'Athena/Glue database name',
      exportName: `${agentName}-athena-database`,
    });

    new cdk.CfnOutput(this, 'AthenaTable', {
      value: this.tableName,
      description: 'Athena table name',
      exportName: `${agentName}-athena-table`,
    });

    new cdk.CfnOutput(this, 'AthenaWorkgroupName', {
      value: workgroup.name!,
      description: 'Athena workgroup name',
      exportName: `${agentName}-athena-workgroup`,
    });

    new cdk.CfnOutput(this, 'UploadLogsCommand', {
      value: `python scripts/upload_logs_to_s3.py --bucket ${logBucket.bucketName} --all`,
      description: 'Command to upload scenario logs to S3',
    });

    new cdk.CfnOutput(this, 'EnvironmentVariables', {
      value: `
# Set these environment variables to use production mode with Athena backend:
export RCA_AGENT_MODE=production
export LOG_SEARCH_BACKEND=athena
export ATHENA_DATABASE=${this.databaseName}
export ATHENA_TABLE=${this.tableName}
export ATHENA_OUTPUT_LOCATION=s3://${resultsBucket.bucketName}/
export AWS_REGION=${this.region}
`.trim(),
    });

    new cdk.CfnOutput(this, 'CostEstimate', {
      value: 'Athena: ~$5 per TB scanned. With partition projection, typical queries scan <1GB (~$0.005/query)',
    });
  }
}
