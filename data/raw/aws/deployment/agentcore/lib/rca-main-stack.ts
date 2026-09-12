import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { AmplifyHostingStack } from './amplify-hosting-stack';
import { AuthStack } from './auth-stack';
import { RcaAgentStack } from './rca-agent-stack';

export interface RcaMainStackProps extends cdk.StackProps {
  agentName: string;
  memoryRetentionDays: number;
  description?: string;
  knowledgeBaseId?: string;
  adminEmail?: string;
  /** Athena database name (from AthenaLogSearchStack). */
  athenaDatabase?: string;
  /** Athena table name (from AthenaLogSearchStack). */
  athenaTable?: string;
  /** Athena results S3 bucket name (from AthenaLogSearchStack). */
  athenaResultsBucket?: string;
}

/**
 * Single parent stack for the RCA Deep Research Agent.
 *
 * Follows the FAST pattern: one parent stack with nested stacks for
 * Amplify Hosting, Cognito Auth, and AgentCore backend resources.
 * All outputs are surfaced on the parent stack for easy querying.
 */
export class RcaMainStack extends cdk.Stack {
  public readonly executionRoleArn: string;

  constructor(scope: Construct, id: string, props: RcaMainStackProps) {
    super(scope, id, props);

    const {
      agentName, memoryRetentionDays, description, knowledgeBaseId, adminEmail,
      athenaDatabase, athenaTable, athenaResultsBucket,
    } = props;

    cdk.Tags.of(this).add('Project', 'rca-deep-research');
    cdk.Tags.of(this).add('ManagedBy', 'cdk');

    // ========================================================================
    // Nested Stack 1: Amplify Hosting
    // ========================================================================
    const amplifyStack = new AmplifyHostingStack(this, 'Amplify', { agentName });

    // ========================================================================
    // Nested Stack 2: Cognito Auth
    // ========================================================================
    const authStack = new AuthStack(this, 'Auth', {
      agentName,
      callbackUrls: [
        'http://localhost:5173',
        'http://localhost:3000',
        amplifyStack.amplifyUrl,
      ],
      logoutUrls: [
        'http://localhost:5173',
        'http://localhost:3000',
        amplifyStack.amplifyUrl,
      ],
      adminEmail,
    });
    authStack.addDependency(amplifyStack);

    // -- Amplify outputs --
    new cdk.CfnOutput(this, 'AmplifyAppId', {
      value: amplifyStack.amplifyApp.attrAppId,
      description: 'Amplify App ID',
    });
    new cdk.CfnOutput(this, 'AmplifyUrl', {
      value: amplifyStack.amplifyUrl,
      description: 'Frontend URL',
    });
    new cdk.CfnOutput(this, 'StagingBucketName', {
      value: amplifyStack.stagingBucket.bucketName,
      description: 'S3 bucket for frontend deployment artifacts',
    });
    new cdk.CfnOutput(this, 'AmplifyConsoleUrl', {
      value: `https://${this.region}.console.aws.amazon.com/amplify/home?region=${this.region}#/${amplifyStack.amplifyApp.attrAppId}`,
      description: 'Amplify Console URL',
    });

    // -- Auth outputs --
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: authStack.userPoolId,
      description: 'Cognito User Pool ID',
    });
    new cdk.CfnOutput(this, 'AppClientId', {
      value: authStack.appClientId,
      description: 'Cognito App Client ID',
    });
    new cdk.CfnOutput(this, 'CognitoDomain', {
      value: authStack.cognitoDomain,
      description: 'Cognito Hosted UI domain',
    });

    // ========================================================================
    // Nested Stack 3: Backend (ECR, IAM, DynamoDB, AgentCore Runtime)
    // ========================================================================
    const agentStack = new RcaAgentStack(this, 'Agent', {
      agentName,
      memoryRetentionDays,
      description,
      knowledgeBaseId,
      cognitoUserPool: authStack.userPool,
      cognitoUserPoolClient: authStack.appClient,
      athenaDatabase,
      athenaTable,
      athenaResultsBucket,
    });
    agentStack.addDependency(authStack);
    this.executionRoleArn = agentStack.executionRoleArn;

    // -- Agent outputs --
    new cdk.CfnOutput(this, 'EcrRepositoryUri', {
      value: agentStack.repositoryUri,
      description: 'ECR repository URI for agent container',
    });
    new cdk.CfnOutput(this, 'ExecutionRoleArn', {
      value: agentStack.executionRoleArn,
      description: 'IAM execution role ARN for AgentCore',
    });
    new cdk.CfnOutput(this, 'CheckpointTableName', {
      value: agentStack.checkpointTableName,
      description: 'DynamoDB table for LangGraph checkpoint persistence',
    });
    new cdk.CfnOutput(this, 'ConfigTableName', {
      value: agentStack.configTableName,
      description: 'DynamoDB table for agent configuration storage',
    });
    new cdk.CfnOutput(this, 'LogGroupName', {
      value: agentStack.logGroupName,
      description: 'CloudWatch log group for agent logs',
    });
    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${agentStack.dashboardName}`,
      description: 'CloudWatch dashboard URL',
    });

    new cdk.CfnOutput(this, 'AgentRuntimeId', {
      value: agentStack.runtimeId,
      description: 'ID of the AgentCore runtime',
    });
    new cdk.CfnOutput(this, 'AgentRuntimeArn', {
      value: agentStack.runtimeArn,
      description: 'ARN of the AgentCore runtime',
    });
    new cdk.CfnOutput(this, 'MemoryArn', {
      value: agentStack.memoryArn,
      description: 'ARN of the AgentCore memory resource',
    });
  }
}
