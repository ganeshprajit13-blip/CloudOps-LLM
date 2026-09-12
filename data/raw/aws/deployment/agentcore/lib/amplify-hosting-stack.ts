import * as cdk from 'aws-cdk-lib';
import * as amplify from 'aws-cdk-lib/aws-amplify';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface AmplifyHostingStackProps extends cdk.NestedStackProps {
  /** Base name for resources (e.g. 'rca-agent'). */
  agentName: string;
}

/**
 * Amplify Hosting for the RCA Deep Research Agent frontend.
 *
 * Deployed as a nested stack inside RcaMainStack.
 */
export class AmplifyHostingStack extends cdk.NestedStack {
  public readonly amplifyApp: amplify.CfnApp;
  public readonly amplifyUrl: string;
  public readonly stagingBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: AmplifyHostingStackProps) {
    super(scope, id, props);

    const { agentName } = props;
    const parentStack = cdk.Stack.of(this);
    const stackNameBase = agentName.replace(/[^a-zA-Z0-9-]/g, '');

    // ==========================================================================
    // S3 Staging Bucket (for manual frontend deployments)
    // ==========================================================================
    const accessLogsBucket = new s3.Bucket(this, 'AccessLogsBucket', {
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(90) }],
    });

    this.stagingBucket = new s3.Bucket(this, 'StagingBucket', {
      bucketName: `${stackNameBase}-frontend-staging-${parentStack.account}-${parentStack.region}`,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'staging-logs/',
      lifecycleRules: [{ expiration: cdk.Duration.days(30) }],
    });

    // ==========================================================================
    // IAM Role for Amplify
    // ==========================================================================
    const amplifyRole = new iam.Role(this, 'AmplifyRole', {
      assumedBy: new iam.ServicePrincipal('amplify.amazonaws.com'),
      description: `Amplify service role for ${agentName} frontend`,
      inlinePolicies: {
        StagingBucketAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['s3:GetObject', 's3:GetObjectVersion', 's3:ListBucket'],
              resources: [
                this.stagingBucket.bucketArn,
                `${this.stagingBucket.bucketArn}/*`,
              ],
            }),
          ],
        }),
      },
    });

    // ==========================================================================
    // Amplify App
    // ==========================================================================
    this.amplifyApp = new amplify.CfnApp(this, 'AmplifyApp', {
      name: `${stackNameBase}-frontend`,
      platform: 'WEB',
      iamServiceRole: amplifyRole.roleArn,
      environmentVariables: [
        { name: 'VITE_AGENTCORE_ENDPOINT', value: '' },
        { name: 'VITE_COGNITO_USER_POOL_ID', value: '' },
        { name: 'VITE_COGNITO_APP_CLIENT_ID', value: '' },
        { name: 'VITE_COGNITO_DOMAIN', value: '' },
        { name: 'VITE_AWS_REGION', value: parentStack.region },
      ],
    });

    // Production branch
    new amplify.CfnBranch(this, 'MainBranch', {
      appId: this.amplifyApp.attrAppId,
      branchName: 'main',
      stage: 'PRODUCTION',
      enableAutoBuild: false,
    });

    // Predictable URL (available before first deployment)
    this.amplifyUrl = `https://main.${this.amplifyApp.attrAppId}.amplifyapp.com`;
  }
}
