import { useMutation, type UseMutationResult } from '@tanstack/react-query'
import { api, raw, clearTokens, setTokens } from './client'
import { type MyPermissions, type TokenPair, type UserPublic } from './types'

// --- Login ------------------------------------------------------------------
// Backend expects OAuth2PasswordRequestForm: form-urlencoded `username`+`password`.
async function loginRequest(email: string, password: string): Promise<TokenPair> {
  const body = new URLSearchParams({ username: email, password })
  const { data } = await raw.post<TokenPair>('/login/access-token', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export interface LoginCredentials {
  email: string
  password: string
}

export function useLogin(): UseMutationResult<
  TokenPair,
  Error,
  LoginCredentials
> {
  return useMutation({
    mutationFn: ({ email, password }) => loginRequest(email, password),
    onSuccess: (tokens) => {
      setTokens(tokens)
    },
  })
}

// --- Current user ------------------------------------------------------------
export async function fetchMe(): Promise<UserPublic> {
  const { data } = await api.get<UserPublic>('/users/me')
  return data
}

// --- Permissions -------------------------------------------------------------
export async function fetchPermissions(): Promise<MyPermissions> {
  const { data } = await api.get<MyPermissions>('/rbac/me/permissions')
  return data
}

// --- Logout ------------------------------------------------------------------
async function logoutRequest(refreshToken: string): Promise<void> {
  await api.post('/logout', { refresh_token: refreshToken, all_sessions: false })
}

export function useLogout(): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: (refreshToken: string) => logoutRequest(refreshToken),
    onSettled: () => {
      clearTokens()
    },
  })
}
