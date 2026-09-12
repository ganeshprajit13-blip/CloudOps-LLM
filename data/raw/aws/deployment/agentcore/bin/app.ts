#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import { IConstruct } from 'constructs';
import { RcaMainStack } from '../lib/rca-main-stack';
import { KnowledgeBaseStack } from '../lib/knowledge-base-stack';
import { AthenaLogSearchStack } from '../lib/athena-log-search-stack';
import { OpenSearchLogSearchStack } from '../lib/opensearch-log-search-stack';

/**
 * CDK Aspect that adds X-Ray tracing and a CloudWatch Errors alarm to every
 * Lambda function in the app. CDK's custom resource providers (e.g.
 * Custom::S3AutoDeleteObjects) use raw CfnResource, not lambda.CfnFunction,
 * so we match on cfnResourceType instead of instanceof.
 */
class LambdaSecurityAspect implements cdk.IAspect {
  public visit(node: IConstruct): void {
    const cfnNode = node as cdk.CfnResource;
    if (cfnNode.cfnResourceType !== 'AWS::Lambda::Function') return;

    // LAMBDA-004: Enable X-Ray tracing
    if (node instanceof lambda.CfnFunction) {
      if (!node.tracingConfig) {
        node.tracingConfig = { mode: 'Active' };
      }
    } else {
      // Raw CfnResource — use property override
      cfnNode.addPropertyOverride('TracingConfig', { Mode: 'Active' });
    }

    // LAMBDA-011: Add CloudWatch Errors alarm
    const stack = cdk.Stack.of(node);
    const alarmId = `${node.node.id}ErrorsAlarm`;
    if (!stack.node.tryFindChild(alarmId)) {
      new cloudwatch.CfnAlarm(stack, alarmId, {
        alarmDescription: `Errors alarm for ${node.node.path}`,
        namespace: 'AWS/Lambda',
        metricName: 'Errors',
        dimensions: [{ name: 'FunctionName', value: cfnNode.ref }],
        statistic: 'Sum',
        period: 300,
        evaluationPeriods: 1,
        threshold: 1,
        comparisonOperator: 'GreaterThanOrEqualToThreshold',
        treatMissingData: 'notBreaching',
      });
    }
  }
}

const app = new cdk.App();

// Get configuration from context
const agentName = app.node.tryGetContext('agentName') || 'rca-agent';
const memoryRetentionDays = app.node.tryGetContext('memoryRetentionDays') || 90;
const syncSampleData = app.node.tryGetContext('syncSampleData') === true ||
                       app.node.tryGetContext('syncSampleData') === 'true';
const deployOpenSearch = app.node.tryGetContext('deployOpenSearch') === true ||
                         app.node.tryGetContext('deployOpenSearch') === 'true';
const knowledgeBaseId = app.node.tryGetContext('knowledgeBaseId');
const adminEmail = app.node.tryGetContext('adminEmail');

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// ==========================================================================
// Knowledge Base Stack (Bedrock KB with S3 Vectors)
// Created before mainStack so the KB ID can be wired into the runtime.
// ==========================================================================

const kbStack = new KnowledgeBaseStack(app, 'RcaKnowledgeBaseStack', {
  agentName,
  syncSampleData,
  description: 'RCA Agent Knowledge Base with S3 Vectors (uksb-v2s6ly2e6z)(tag:knowledge-base)',
  env,
});

// ==========================================================================
// Athena Log Search Stack (S3 + Glue + Athena — default log backend)
// Created before mainStack so Athena config can be wired into the runtime.
// ==========================================================================

const athenaStack = new AthenaLogSearchStack(app, 'RcaAthenaLogSearchStack', {
  agentName,
  description: 'RCA Agent Athena Log Search (uksb-v2s6ly2e6z)(tag:athena)',
  env,
});

// ==========================================================================
// Main Stack (parent with nested stacks: Amplify, Auth, Agent)
// ==========================================================================

// Context knowledgeBaseId overrides the deployed KB (for users with existing KBs)
const effectiveKbId = knowledgeBaseId || kbStack.knowledgeBaseId;

const mainStack = new RcaMainStack(app, 'RcaStack', {
  agentName,
  memoryRetentionDays,
  description: 'Deep Research RCA Agent with Human-in-the-Loop (uksb-v2s6ly2e6z)(tag:deploy)',
  knowledgeBaseId: effectiveKbId,
  adminEmail,
  athenaDatabase: athenaStack.databaseName,
  athenaTable: athenaStack.tableName,
  athenaResultsBucket: athenaStack.resultsBucketName,
  env,
});
mainStack.addDependency(kbStack);
mainStack.addDependency(athenaStack);

// ==========================================================================
// Optional: OpenSearch Serverless (~$350/month min, sub-second queries)
// ==========================================================================

if (deployOpenSearch) {
  const opensearchStack = new OpenSearchLogSearchStack(app, 'RcaOpenSearchLogSearchStack', {
    agentName,
    agentRoleArn: mainStack.executionRoleArn,
    description: 'RCA Agent OpenSearch Serverless Log Search (uksb-v2s6ly2e6z)(tag:opensearch)',
    env,
  });
  opensearchStack.addDependency(mainStack);
}

// ==========================================================================
// Security Aspects — applied globally to all stacks
// ==========================================================================
cdk.Aspects.of(app).add(new LambdaSecurityAspect());

app.synth();
