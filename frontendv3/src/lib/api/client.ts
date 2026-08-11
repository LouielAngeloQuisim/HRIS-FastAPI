import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios'
import { getCookie, setCookie, removeCookie } from '@/lib/cookies'
import { type ErrorResponse, type TokenPair } from './types'

const ACCESS_TOKEN_COOKIE = 'hris_at'
const REFRESH_TOKEN_COOKIE = 'hris_rt'
const TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // 7 days (>= refresh lifetime)

export function getAccessToken(): string | undefined {
  return getCookie(ACCESS_TOKEN_COOKIE)
}

export function getRefreshToken(): string | undefined {
  return getCookie(REFRESH_TOKEN_COOKIE)
}

export function setTokens(tokens: TokenPair): void {
  setCookie(ACCESS_TOKEN_COOKIE, tokens.access_token, TOKEN_COOKIE_MAX_AGE)
  setCookie(REFRESH_TOKEN_COOKIE, tokens.refresh_token, TOKEN_COOKIE_MAX_AGE)
}

export function clearTokens(): void {
  removeCookie(ACCESS_TOKEN_COOKIE)
  removeCookie(REFRESH_TOKEN_COOKIE)
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const API_V1 = `${API_URL}/api/v1`

export const api = axios.create({
  baseURL: API_V1,
  headers: { 'Content-Type': 'application/json' },
  // Never let axios retry automatically; refresh is handled by the interceptor.
  // Each request carries a custom flag so we only attempt one refresh per chain.
})

// --- Request interceptor: attach bearer token -------------------------------
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

// --- Response interceptor: single-use refresh on 401 -------------------------
let refreshInFlight: Promise<TokenPair> | null = null

async function doRefresh(): Promise<TokenPair> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    throw new Error('No refresh token available')
  }
  // Backend rotates the refresh token — single-use — so this request goes straight
  // to the raw instance to avoid a recursive 401 loop.
  const { data } = await raw.post<TokenPair>('/login/refresh-token', {
    refresh_token: refreshToken,
  })
  setTokens(data)
  return data
}

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/login/refresh-token')
    ) {
      originalRequest._retry = true
      try {
        if (!refreshInFlight) {
          refreshInFlight = doRefresh().finally(() => {
            refreshInFlight = null
          })
        }
        await refreshInFlight
        const token = getAccessToken()
        if (token) {
          originalRequest.headers.set('Authorization', `Bearer ${token}`)
        }
        return api(originalRequest)
      } catch {
        clearTokens()
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  }
)

// Raw instance (no interceptors) for the refresh call and any public endpoints.
export const raw = axios.create({
  baseURL: API_V1,
  headers: { 'Content-Type': 'application/json' },
})

export function getErrorResponse(error: unknown): ErrorResponse | null {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === 'object' && 'error' in data) {
      return data as ErrorResponse
    }
  }
  return null
}
