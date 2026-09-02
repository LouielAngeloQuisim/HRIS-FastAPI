/**
 * Cookie utility functions using manual document.cookie approach
 * Replaces js-cookie dependency for better consistency
 */

const DEFAULT_MAX_AGE = 60 * 60 * 24 * 7 // 7 days

// Production security flags - HTTPS only, HttpOnly, SameSite strict
// Note: HttpOnly flag cannot be set from JavaScript - it's server-side only
// We'll focus on flags that can be set from client-side

export const COOKIE_FLAGS_PROD = '; SameSite=Strict; Secure'
export const COOKIE_FLAGS_DEV = '; SameSite=Lax'

/**
 * Whether the current page is being served over HTTPS.
 */
export function isHttps(): boolean {
  if (typeof window === 'undefined') return false
  return window.location.protocol === 'https:'
}

const getCookieSecurityFlags = (): string =>
  isHttps() ? COOKIE_FLAGS_PROD : COOKIE_FLAGS_DEV

/**
 * Get a cookie value by name
 */
export function getCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined

  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    const cookieValue = parts.pop()?.split(';').shift()
    return cookieValue
  }
  return undefined
}

/**
 * Set a cookie with name, value, and optional max age
 */
export function setCookie(
  name: string,
  value: string,
  maxAge: number = DEFAULT_MAX_AGE
): void {
  if (typeof document === 'undefined') return

  // Special handling for auth tokens
  const isAuthToken = name === 'hris_at' || name === 'hris_rt'

  if (isAuthToken) {
    const flags = isHttps() ? COOKIE_FLAGS_PROD : COOKIE_FLAGS_DEV
    document.cookie = `${name}=${value}; path=/; max-age=${maxAge}${flags}`
  } else {
    const securityFlags = getCookieSecurityFlags()
    document.cookie = `${name}=${value}; path=/; max-age=${maxAge}${securityFlags}`
  }
}

/**
 * Remove a cookie by setting its max age to 0
 */
export function removeCookie(name: string): void {
  if (typeof document === 'undefined') return

  const securityFlags = getCookieSecurityFlags()
  document.cookie = `${name}=; path=/; max-age=0${securityFlags}`
}


