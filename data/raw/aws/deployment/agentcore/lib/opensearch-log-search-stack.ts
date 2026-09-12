import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import { Construct } from 'constructs';

export interface OpenSearchLogSearchStackProps extends cdk.StackProps {
  agentName: string;
  agentRoleArn: string;
}

/**
 * OpenSearch Serverless Stack for RCA Agent.
 *
 * Creates infrastructure for sub-second log queries using OpenSearch Serverless:
 * - AOSS collection (type: SEARCH)
 * - Encryption, network, and data access policies
 * - IAM permissions for the agent execution role
 *
 * Cost: ~$350/month minimum (2 OCU baseline for indexing + search).
 * Only deployed when `-c deployOpenSearch=true`.
 */
export class OpenSearchLogSearchStack extends cdk.Stack {
  public readonly collectionEndpoint: string;
  public readonly collectionArn: string;
  public readonly collectionName: string;

  constructor(scope: Construct, id: string, props: OpenSearchLogSearchStackProps) {
    super(scope, id, props);

    const { agentName, agentRoleArn } = props;

    // Collection name must be lowercase, <= 32 chars
    const collectionName = `${agentName}-logs`.substring(0, 32).toLowerCase();

    // ==========================================================================
    // Resource Tags
    // ==========================================================================
    cdk.Tags.of(this).add('Project', 'rca-deep-research');
    cdk.Tags.of(this).add('Component', 'opensearch-log-search');
    cdk.Tags.of(this).add('ManagedBy', 'cdk');

    // ==========================================================================
    // Encryption Policy (required before collection creation)
    // ==========================================================================
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: `${collectionName}-enc`,
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [
          {
            Resource: [`collection/${collectionName}`],
            ResourceType: 'collection',
          },
        ],
        AWSOwnedKey: true,
      }),
    });

    // ==========================================================================
    // Network Policy (public access — same simplicity as Athena stack)
    // ==========================================================================
    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: `${collectionName}-net`,
      type: 'network',
      policy: JSON.stringify([
        {
          Rules: [
            {
              Resource: [`collection/${collectionName}`],
              ResourceType: 'collection',
            },
            {
              Resource: [`collection/${collectionName}`],
              ResourceType: 'dashboard',
            },
          ],
          AllowFromPublic: true,
        },
      ]),
    });

    // ==========================================================================
    // AOSS Collection
    // ==========================================================================
    const collection = new opensearchserverless.CfnCollection(this, 'LogCollection', {
      name: collectionName,
      type: 'SEARCH',
      description: 'RCA Agent log collection for sub-second queries',
    });

    collection.addDependency(encryptionPolicy);
    collection.addDependency(networkPolicy);

    this.collectionName = collectionName;
    this.collectionEndpoint = collection.attrCollectionEndpoint;
    this.collectionArn = collection.attrArn;

    // ==========================================================================
    // Data Access Policy (grants agent role index-level access)
    // ==========================================================================
    new opensearchserverless.CfnAccessPolicy(this, 'DataAccessPolicy', {
      name: `${collectionName}-access`,
      type: 'data',
      policy: JSON.stringify([
        {
          Rules: [
            {
              Resource: [`collection/${collectionName}`],
              ResourceType: 'collection',
              Permission: [
                'aoss:CreateCollectionItems',
                'aoss:DescribeCollectionItems',
                'aoss:UpdateCollectionItems',
              ],
            },
            {
              Resource: [`index/${collectionName}/*`],
              ResourceType: 'index',
              Permission: [
                'aoss:CreateIndex',
                'aoss:DescribeIndex',
                'aoss:UpdateIndex',
                'aoss:ReadDocument',
                'aoss:WriteDocument',
              ],
            },
          ],
          Principal: [agentRoleArn, `arn:aws:iam::${this.account}:root`],
        },
      ]),
    });

    // ==========================================================================
    // IAM: Grant agent role AOSS API access
    // ==========================================================================
    const agentRole = iam.Role.fromRoleArn(this, 'AgentRole', agentRoleArn);

    new iam.Policy(this, 'AossApiAccess', {
      roles: [agentRole],
      statements: [
        new iam.PolicyStatement({
          actions: ['aoss:APIAccessAll'],
          resources: [collection.attrArn],
        }),
      ],
    });

    // ==========================================================================
    // Outputs
    // ==========================================================================
    new cdk.CfnOutput(this, 'CollectionEndpoint', {
      value: collection.attrCollectionEndpoint,
      description: 'OpenSearch Serverless collection endpoint',
      exportName: `${agentName}-opensearch-endpoint`,
    });

    new cdk.CfnOutput(this, 'CollectionArn', {
      value: collection.attrArn,
      description: 'OpenSearch Serverless collection ARN',
      exportName: `${agentName}-opensearch-arn`,
    });

    new cdk.CfnOutput(this, 'CollectionName', {
      value: collectionName,
      description: 'OpenSearch Serverless collection name',
      exportName: `${agentName}-opensearch-collection`,
    });

    new cdk.CfnOutput(this, 'EnvironmentVariables', {
      value: `
# Set these environment variables to use production mode with OpenSearch backend:
export RCA_AGENT_MODE=production
export LOG_SEARCH_BACKEND=opensearch
export OPENSEARCH_ENDPOINT=\${${collection.attrCollectionEndpoint}}
export OPENSEARCH_INDEX=rca-logs
export OPENSEARCH_AUTH_MODE=iam
export OPENSEARCH_SERVERLESS=true
export AWS_REGION=${this.region}
`.trim(),
    });

    new cdk.CfnOutput(this, 'CostEstimate', {
      value: 'OpenSearch Serverless: ~$350/month minimum (2 OCU baseline). Sub-second query latency.',
    });
  }
}
