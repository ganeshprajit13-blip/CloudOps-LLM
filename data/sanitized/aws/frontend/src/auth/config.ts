/**
 * Amplify Auth configuration from environment variables.
 *
 * In production, these are set via Amplify Hosting environment variables
 * (populated from CDK outputs). In local dev, they are empty and auth
 * is bypassed entirely.
 */

export const cognitoConfig = {
  userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
  appClientId: import.meta.env.VITE_COGNITO_APP_CLIENT_ID || '',
  domain: import.meta.env.VITE_COGNITO_DOMAIN || '',
  region: import.meta.env.VITE_AWS_REGION || 'us-east-1',
}

/** True when all required Cognito values are configured (production deployment). */
export const isAuthEnabled =
  !!cognitoConfig.userPoolId && !!cognitoConfig.appClientId && !!cognitoConfig.domain
