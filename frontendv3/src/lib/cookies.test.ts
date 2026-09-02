import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  COOKIE_FLAGS_DEV,
  COOKIE_FLAGS_PROD,
  getCookie,
  removeCookie,
  setCookie,
} from './cookies'

const COOKIE_PREFIX = 'test_cookie_'

describe('cookies', () => {
  const uniqueName = () =>
    `${COOKIE_PREFIX}${Math.random().toString(36).slice(2)}`

  beforeEach(() => {
    // Clear document.cookie between tests.
    document.cookie.split(';').forEach((part) => {
      const name = part.split('=')[0]?.trim()
      if (name) {
        document.cookie = `${name}=; path=/; max-age=0`
      }
    })
  })

  it('stores a value that can be read back', () => {
    const name = uniqueName()
    const value = 'hello-world'

    setCookie(name, value)

    expect(getCookie(name)).toBe(value)
  })

  it('clears a value so it is no longer readable', () => {
    const name = uniqueName()

    setCookie(name, 'x')
    expect(getCookie(name)).toBe('x')

    removeCookie(name)

    expect(getCookie(name)).toBeUndefined()
  })

  describe('security flag constants', () => {
    it('COOKIE_FLAGS_PROD uses SameSite=Strict and Secure', () => {
      expect(COOKIE_FLAGS_PROD).toContain('SameSite=Strict')
      expect(COOKIE_FLAGS_PROD).toContain('Secure')
    })

    it('COOKIE_FLAGS_DEV uses SameSite=Lax without Secure', () => {
      expect(COOKIE_FLAGS_DEV).toContain('SameSite=Lax')
      expect(COOKIE_FLAGS_DEV).not.toContain('Secure')
    })
  })

  describe('default (runtime protocol = http:)', () => {
    it('non-auth cookies are set with SameSite=Lax and no Secure', () => {
      const setSpy = vi.spyOn(document, 'cookie', 'set')
      const name = uniqueName()
      setCookie(name, 'v')
      const last = setSpy.mock.calls.at(-1)?.[0] as string
      expect(last).toContain(`${name}=v`)
      expect(last).toContain(COOKIE_FLAGS_DEV)
      expect(last).not.toContain('Secure')
      setSpy.mockRestore()
    })

    it('hris_at uses SameSite=Lax and no Secure', () => {
      const setSpy = vi.spyOn(document, 'cookie', 'set')
      setCookie('hris_at', 'token-value')
      const last = setSpy.mock.calls.at(-1)?.[0] as string
      expect(last).toMatch(/^hris_at=token-value/)
      expect(last).toContain(COOKIE_FLAGS_DEV)
      expect(last).not.toContain('Secure')
      setSpy.mockRestore()
    })

    it('removeCookie uses SameSite=Lax without Secure', () => {
      const setSpy = vi.spyOn(document, 'cookie', 'set')
      removeCookie('foo')
      const last = setSpy.mock.calls.at(-1)?.[0] as string
      expect(last).toContain('foo=;')
      expect(last).toContain(COOKIE_FLAGS_DEV)
      expect(last).not.toContain('Secure')
      setSpy.mockRestore()
    })
  })
})






