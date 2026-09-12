/**
 * Cognito authentication context for the RCA Deep Research Agent.
 *
 * When Cognito is configured (production), this uses @aws-amplify/auth
 * for Hosted UI sign-in/out and JWT token management. When Cognito is
 * not configured (local dev), auth is bypassed — all operations are
 * no-ops and getAccessToken returns null.
 */

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'
import { Amplify } from 'aws-amplify'
import { signOut, getCurrentUser, fetchAuthSession, fetchUserAttributes, signInWithRedirect } from 'aws-amplify/auth'
import { Hub } from 'aws-amplify/utils'
import { cognitoConfig, isAuthEnabled } from './config'

/** Clear stale Cognito tokens from localStorage.
 *
 * After a redeployment that creates a new User Pool or App Client, old refresh
 * tokens may linger and cause HTTP 400 from Cognito's GetTokensFromRefreshToken.
 * Clearing them forces a fresh sign-in. */
function clearAmplifyStorage() {
  if (typeof window === 'undefined' || !window.localStorage) return
  const keysToRemove: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith('CognitoIdentityServiceProvider.')) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach(k => localStorage.removeItem(k))
}

interface AuthUser {
  username: string
  email?: string
}

interface AuthContextValue {
  /** Current authenticated user, or null if not signed in. */
  user: AuthUser | null
  /** True while the initial auth check is in progress. */
  loading: boolean
  /** True when Cognito auth is configured (production mode). */
  authEnabled: boolean
  /** Redirect to Cognito Hosted UI for sign-in. */
  handleSignIn: () => Promise<void>
  /** Sign out and redirect to Cognito logout. */
  handleSignOut: () => Promise<void>
  /** Get the current access token (JWT) for API calls. Returns null in local dev. */
  getAccessToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  authEnabled: false,
  handleSignIn: async () => {},
  handleSignOut: async () => {},
  getAccessToken: async () => null,
})

// Configure Amplify once at module load
if (isAuthEnabled) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: cognitoConfig.userPoolId,
        userPoolClientId: cognitoConfig.appClientId,
        loginWith: {
          oauth: {
            domain: cognitoConfig.domain,
            scopes: ['openid', 'email', 'profile'],
            redirectSignIn: [window.location.origin],
            redirectSignOut: [window.location.origin],
            responseType: 'code',
          },
        },
      },
    },
  })
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(isAuthEnabled)

  // Resolve the current user's email from multiple sources (attributes, ID token, signInDetails)
  const resolveUser = useCallback(async () => {
    try {
      const cognitoUser = await getCurrentUser()
      let email: string | undefined

      // Try fetchUserAttributes first (needs ReadAttributes on the app client)
      try {
        const attrs = await fetchUserAttributes()
        email = attrs.email
      } catch { /* fall through */ }

      // Fallback: extract email from the ID token payload
      if (!email) {
        try {
          const session = await fetchAuthSession({ forceRefresh: false })
          email = session.tokens?.idToken?.payload?.email as string | undefined
        } catch { /* fall through */ }
      }

      // Last resort: signInDetails (only populated for direct sign-in, not redirects)
      if (!email) {
        email = cognitoUser.signInDetails?.loginId
      }

      setUser({ username: cognitoUser.username, email })
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Check for existing session on mount + listen for OAuth redirect completion
  useEffect(() => {
    if (!isAuthEnabled) return

    resolveUser()

    // After signInWithRedirect, the page reloads and Hub fires this event
    // once the authorization code exchange completes
    const unsubscribe = Hub.listen('auth', ({ payload }) => {
      if (payload.event === 'signInWithRedirect') {
        resolveUser()
      }
      if (payload.event === 'tokenRefresh_failure') {
        console.error('Token refresh failed, clearing stale session')
        clearAmplifyStorage()
        setUser(null)
      }
    })
    return unsubscribe
  }, [resolveUser])

  const handleSignIn = useCallback(async () => {
    if (!isAuthEnabled) return
    try {
      await signInWithRedirect()
    } catch (err) {
      // If already signed in, try regular signIn flow
      console.error('Sign-in redirect failed:', err)
    }
  }, [])

  const handleSignOut = useCallback(async () => {
    if (!isAuthEnabled) return
    try {
      await signOut({ global: true })
      setUser(null)
    } catch (err) {
      console.error('Sign-out failed:', err)
    }
  }, [])

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!isAuthEnabled) return null
    try {
      // fetchAuthSession auto-refreshes expired tokens via the refresh token
      const session = await fetchAuthSession({ forceRefresh: false })
      const token = session.tokens?.accessToken?.toString() ?? null
      if (!token) {
        clearAmplifyStorage()
        throw new Error('No access token available — please sign in again')
      }
      return token
    } catch (err) {
      console.error('Failed to get access token:', err)
      clearAmplifyStorage()
      throw new Error(
        `Authentication failed: ${err instanceof Error ? err.message : 'unknown error'}. Please sign in again.`
      )
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        authEnabled: isAuthEnabled,
        handleSignIn,
        handleSignOut,
        getAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
