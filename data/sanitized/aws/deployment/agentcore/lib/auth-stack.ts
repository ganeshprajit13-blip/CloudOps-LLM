import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';

export interface AuthStackProps extends cdk.NestedStackProps {
  /** Base name for resources (e.g. 'rca-agent'). */
  agentName: string;
  /** Callback URLs for the Cognito Hosted UI (must include Amplify URL). */
  callbackUrls: string[];
  /** Logout URLs (must include Amplify URL). */
  logoutUrls: string[];
  /** Optional admin email — if provided, creates an initial admin user. */
  adminEmail?: string;
}

/**
 * Cognito User Pool and App Client for the RCA Deep Research Agent.
 *
 * Deployed as a nested stack inside RcaMainStack.
 */
export class AuthStack extends cdk.NestedStack {
  public readonly userPoolId: string;
  public readonly userPoolArn: string;
  public readonly appClientId: string;
  public readonly cognitoDomain: string;
  public readonly userPool: cognito.UserPool;
  public readonly appClient: cognito.UserPoolClient;

  constructor(scope: Construct, id: string, props: AuthStackProps) {
    super(scope, id, props);

    const { agentName, callbackUrls, logoutUrls, adminEmail } = props;
    const parentStack = cdk.Stack.of(this);

    // ==========================================================================
    // Cognito User Pool
    // ==========================================================================
    const userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `${agentName}-users`,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
      },
      passwordPolicy: {
        minLength: 8,
        requireUppercase: true,
        requireLowercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.userPool = userPool;
    this.userPoolId = userPool.userPoolId;
    this.userPoolArn = userPool.userPoolArn;

    // ==========================================================================
    // User Pool Domain (Cognito Hosted UI)
    // ==========================================================================
    const stackNameBase = agentName.replace(/[^a-zA-Z0-9-]/g, '');
    const domainPrefix = `${stackNameBase}-${parentStack.account}-${parentStack.region}`;

    userPool.addDomain('CognitoDomain', {
      cognitoDomain: { domainPrefix },
    });

    this.cognitoDomain = `${domainPrefix}.auth.${parentStack.region}.amazoncognito.com`;

    // ==========================================================================
    // App Client (frontend)
    // ==========================================================================
    const appClient = userPool.addClient('FrontendClient', {
      userPoolClientName: `${agentName}-frontend`,
      generateSecret: false,
      authFlows: {
        userPassword: true,
        userSrp: true,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls,
        logoutUrls,
      },
      preventUserExistenceErrors: true,
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
    });

    this.appClient = appClient;
    this.appClientId = appClient.userPoolClientId;

    // ==========================================================================
    // Optional: Create admin user
    // ==========================================================================
    if (adminEmail) {
      new cognito.CfnUserPoolUser(this, 'AdminUser', {
        userPoolId: userPool.userPoolId,
        username: adminEmail,
        userAttributes: [
          { name: 'email', value: adminEmail },
          { name: 'email_verified', value: 'true' },
        ],
        desiredDeliveryMediums: ['EMAIL'],
      });
    }
  }
}
