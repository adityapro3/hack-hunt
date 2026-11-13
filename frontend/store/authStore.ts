import { create } from 'zustand'
import type { AuthUser } from '@/lib/types'
import {
  clearAuthSessionStorage,
  getAuthSession,
  saveAuthSession,
  type AuthSession,
} from '@/lib/auth'

interface AuthState {
  accessToken: string | null
  tokenType: string | null
  user: AuthUser | null
  hydrated: boolean
  initialize: () => void
  setSession: (session: AuthSession) => void
  setUser: (user: AuthUser) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  tokenType: null,
  user: null,
  hydrated: false,
  initialize: () => {
    const session = getAuthSession()
    if (!session) {
      set({ hydrated: true })
      return
    }

    set({
      accessToken: session.access_token,
      tokenType: session.token_type,
      user: session.user,
      hydrated: true,
    })
  },
  setSession: (session) => {
    saveAuthSession(session)
    set({
      accessToken: session.access_token,
      tokenType: session.token_type,
      user: session.user,
      hydrated: true,
    })
  },
  setUser: (user) => {
    const current = getAuthSession()
    if (current) {
      saveAuthSession({ ...current, user })
    }
    set({ user })
  },
  clearSession: () => {
    clearAuthSessionStorage()
    set({
      accessToken: null,
      tokenType: null,
      user: null,
      hydrated: true,
    })
  },
}))
