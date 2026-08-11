import { create } from 'zustand'
import { setCookie, removeCookie } from '@/lib/cookies'
import {
  getAccessToken,
  getRefreshToken,
  clearTokens,
} from '@/lib/api/client'
import { type MyPermissions, type UserPublic } from '@/lib/api/types'

const ACCESS_TOKEN = 'hris_at'

interface AuthUser {
  id: string
  email: string
  fullName: string | null
  isSuperuser: boolean
  roleId: string | null
  roleCode: string | null
}

interface AuthState {
  auth: {
    user: AuthUser | null
    setUser: (user: AuthUser | null) => void
    accessToken: string
    setAccessToken: (accessToken: string) => void
    resetAccessToken: () => void
    reset: () => void
    bootstrapFromStorage: () => void
    setPermissions: (permissions: MyPermissions | null) => void
    permissions: MyPermissions | null
  }
}

function toAuthUser(
  user: UserPublic,
  roleCode: string | null
): AuthUser {
  return {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    isSuperuser: user.is_superuser,
    roleId: user.role_id,
    roleCode,
  }
}

export const useAuthStore = create<AuthState>()((set) => {
  const initToken = getAccessToken() ?? ''
  return {
    auth: {
      user: null,
      setUser: (user) =>
        set((state) => ({ ...state, auth: { ...state.auth, user } })),
      accessToken: initToken,
      setAccessToken: (accessToken) => {
        if (accessToken) setCookie(ACCESS_TOKEN, accessToken, 60 * 60 * 24 * 7)
        return set((state) => ({
          ...state,
          auth: { ...state.auth, accessToken },
        }))
      },
      resetAccessToken: () => {
        removeCookie(ACCESS_TOKEN)
        return set((state) => ({
          ...state,
          auth: { ...state.auth, accessToken: '' },
        }))
      },
      reset: () => {
        clearTokens()
        removeCookie(ACCESS_TOKEN)
        return set((state) => ({
          ...state,
          auth: {
            ...state.auth,
            user: null,
            accessToken: '',
            permissions: null,
          },
        }))
      },
      bootstrapFromStorage: () => {
        const access = getAccessToken()
        const refresh = getRefreshToken()
        return set((state) => ({
          ...state,
          auth: {
            ...state.auth,
            accessToken: access ?? state.auth.accessToken,
            // A session is only considered "present" if both tokens exist.
            user: access && refresh ? state.auth.user : null,
          },
        }))
      },
      setPermissions: (permissions) =>
        set((state) => ({
          ...state,
          auth: { ...state.auth, permissions },
        })),
      permissions: null,
    },
  }
})

export { toAuthUser, ACCESS_TOKEN }
