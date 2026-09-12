import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { RcaMainStack } from '../lib/rca-main-stack';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TEST_ENV = { account: '123456789012', region: 'us-east-1' };
const AGENT_NAME = 'rca-agent';

function createMainStack(overrides: Partial<{
  adminEmail: string;
  knowledgeBaseId: string;
  athenaDatabase: string;
  athenaTable: string;
  athenaResultsBucket: string;
}> = {}): { stack: RcaMainStack; template: Template } {
  const app = new cdk.App();
  const stack = new RcaMainStack(app, 'TestRcaStack', {
    agentName: AGENT_NAME,
    memoryRetentionDays: 90,
    description: 'Test stack',
    env: TEST_ENV,
    ...overrides,
  });
  return { stack, template: Template.fromStack(stack) };
}

// ===========================================================================
// Parent Stack — always creates 3 nested stacks (Amplify, Auth, Agent)
// ===========================================================================

describe('RcaMainStack', () => {
  test('creates 3 nested stacks (Amplify, Auth, Agent)', () => {
    const { template } = createMainStack();
    template.resourceCountIs('AWS::CloudFormation::Stack', 3);
  });

  test('has Amplify outputs', () => {
    const { template } = createMainStack();
    template.hasOutput('AmplifyAppId', {});
    template.hasOutput('AmplifyUrl', {});
    template.hasOutput('StagingBucketName', {});
  });

  test('has Auth outputs', () => {
    const { template } = createMainStack();
    template.hasOutput('UserPoolId', {});
    template.hasOutput('AppClientId', {});
    template.hasOutput('CognitoDomain', {});
  });

  test('has Agent outputs', () => {
    const { template } = createMainStack();
    template.hasOutput('EcrRepositoryUri', {});
    template.hasOutput('ExecutionRoleArn', {});
    template.hasOutput('CheckpointTableName', {});
    template.hasOutput('ConfigTableName', {});
    template.hasOutput('LogGroupName', {});
    template.hasOutput('DashboardUrl', {});
  });

  test('always has AgentCore runtime outputs', () => {
    const { template } = createMainStack();
    template.hasOutput('AgentRuntimeId', {});
    template.hasOutput('AgentRuntimeArn', {});
    template.hasOutput('MemoryArn', {});
  });
});

// ===========================================================================
// Nested stack internals — Auth
// ===========================================================================

describe('Auth nested stack', () => {
  test('creates a Cognito User Pool with email sign-in', () => {
    const app = new cdk.App();
    const parentStack = new cdk.Stack(app, 'Parent', { env: TEST_ENV });

    // Import AuthStack to test it in isolation as a nested stack
    const { AuthStack } = require('../lib/auth-stack');
    const auth = new AuthStack(parentStack, 'Auth', {
      agentName: AGENT_NAME,
      callbackUrls: ['http://localhost:5173'],
      logoutUrls: ['http://localhost:5173'],
    });

    const template = Template.fromStack(auth);
    template.hasResourceProperties('AWS::Cognito::UserPool', {
      UserPoolName: `${AGENT_NAME}-users`,
      AutoVerifiedAttributes: ['email'],
      UsernameAttributes: ['email'],
      Policies: Match.objectLike({
        PasswordPolicy: Match.objectLike({ MinimumLength: 8 }),
      }),
    });
  });

  test('creates App Client with OAuth2 authorization code grant', () => {
    const app = new cdk.App();
    const parentStack = new cdk.Stack(app, 'Parent', { env: TEST_ENV });

    const { AuthStack } = require('../lib/auth-stack');
    const auth = new AuthStack(parentStack, 'Auth', {
      agentName: AGENT_NAME,
      callbackUrls: ['http://localhost:5173'],
      logoutUrls: ['http://localhost:5173'],
    });

    const template = Template.fromStack(auth);
    template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
      ClientName: `${AGENT_NAME}-frontend`,
      GenerateSecret: false,
      AllowedOAuthFlows: ['code'],
      AllowedOAuthScopes: Match.arrayWith(['openid', 'email', 'profile']),
      PreventUserExistenceErrors: 'ENABLED',
    });
  });

  test('optional admin user is created when adminEmail is provided', () => {
    const app = new cdk.App();
    const parentStack = new cdk.Stack(app, 'Parent', { env: TEST_ENV });

    const { AuthStack } = require('../lib/auth-stack');
    const auth = new AuthStack(parentStack, 'Auth', {
      agentName: AGENT_NAME,
      callbackUrls: ['http://localhost:5173'],
      logoutUrls: ['http://localhost:5173'],
      adminEmail: 'admin@example.com',
    });

    const template = Template.fromStack(auth);
    template.hasResourceProperties('AWS::Cognito::UserPoolUser', {
      Username: 'admin@example.com',
    });
  });
});

// ===========================================================================
// Nested stack internals — Amplify
// ===========================================================================

describe('Amplify nested stack', () => {
  test('creates an Amplify CfnApp and CfnBranch', () => {
    const app = new cdk.App();
    const parentStack = new cdk.Stack(app, 'Parent', { env: TEST_ENV });

    const { AmplifyHostingStack } = require('../lib/amplify-hosting-stack');
    const amplify = new AmplifyHostingStack(parentStack, 'Amplify', {
      agentName: AGENT_NAME,
    });

    const template = Template.fromStack(amplify);
    template.hasResourceProperties('AWS::Amplify::App', {
      Name: Match.stringLikeRegexp(`^${AGENT_NAME}`),
      Platform: 'WEB',
    });
    template.hasResourceProperties('AWS::Amplify::Branch', {
      BranchName: 'main',
      Stage: 'PRODUCTION',
      EnableAutoBuild: false,
    });
  });

  test('creates S3 staging bucket with versioning', () => {
    const app = new cdk.App();
    const parentStack = new cdk.Stack(app, 'Parent', { env: TEST_ENV });

    const { AmplifyHostingStack } = require('../lib/amplify-hosting-stack');
    const amplify = new AmplifyHostingStack(parentStack, 'Amplify', {
      agentName: AGENT_NAME,
    });

    const template = Template.fromStack(amplify);
    template.hasResourceProperties('AWS::S3::Bucket', {
      BucketName: Match.stringLikeRegexp(`^${AGENT_NAME}.*frontend-staging`),
      VersioningConfiguration: { Status: 'Enabled' },
    });
  });
});

// ===========================================================================
// Integration: full synthesis
// ===========================================================================

describe('Integration', () => {
  test('synthesis produces a single parent stack with all outputs', () => {
    const { stack, template } = createMainStack({
      adminEmail: 'admin@example.com',
    });

    // Single parent stack name
    expect(stack.stackName).toBe('TestRcaStack');

    // All outputs are on the parent
    template.hasOutput('AmplifyUrl', {});
    template.hasOutput('UserPoolId', {});
    template.hasOutput('CheckpointTableName', {});

    // 3 nested stacks
    template.resourceCountIs('AWS::CloudFormation::Stack', 3);
  });
});
