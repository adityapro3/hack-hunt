import type { AuthUser } from '@/lib/types'

const AUTH_SESSION_KEY = 'hack_hunt_auth_session'

export interface AuthSession {
  access_token: string
  token_type: string
  user: AuthUser
}

export function getAuthSession(): AuthSession | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(AUTH_SESSION_KEY)
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw) as AuthSession
    if (!parsed.access_token || !parsed.token_type || !parsed.user) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function saveAuthSession(session: AuthSession): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session))
}

export function clearAuthSessionStorage(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.removeItem(AUTH_SESSION_KEY)
}
