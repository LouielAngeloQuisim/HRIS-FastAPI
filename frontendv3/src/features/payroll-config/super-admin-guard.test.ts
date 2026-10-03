import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getStateMock, fetchMeMock } = vi.hoisted(() => ({ getStateMock: vi.fn(), fetchMeMock: vi.fn() }))
vi.mock('@tanstack/react-router', () => ({ redirect: (opts: { to: string }) => new Error(`redirect:${opts.to}`) }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: { getState: () => getStateMock() } }))
vi.mock('@/lib/api/auth', () => ({ fetchMe: fetchMeMock }))
import { assertSuperAdmin } from './super-admin-guard'

describe('payroll-config super-admin guard', () => {
  beforeEach(() => vi.clearAllMocks())
  it('blocks cached non-superusers without another request', async () => {
    getStateMock.mockReturnValue({ auth: { user: { isSuperuser: false } } })
    await expect(assertSuperAdmin()).rejects.toThrow(/redirect/)
    expect(fetchMeMock).not.toHaveBeenCalled()
  })
  it('allows cached superusers', async () => {
    getStateMock.mockReturnValue({ auth: { user: { isSuperuser: true } } })
    await expect(assertSuperAdmin()).resolves.toBeUndefined()
  })
  it('allows an authenticated superuser before store hydration', async () => {
    getStateMock.mockReturnValue({ auth: { user: null } })
    fetchMeMock.mockResolvedValue({ is_superuser: true })
    await expect(assertSuperAdmin()).resolves.toBeUndefined()
  })
  it('blocks a fetched non-superuser', async () => {
    getStateMock.mockReturnValue({ auth: { user: null } })
    fetchMeMock.mockResolvedValue({ is_superuser: false })
    await expect(assertSuperAdmin()).rejects.toThrow(/redirect/)
  })
  it('fails closed when authentication fails', async () => {
    getStateMock.mockReturnValue({ auth: { user: null } })
    fetchMeMock.mockRejectedValue(new Error('unauthenticated'))
    await expect(assertSuperAdmin()).rejects.toThrow(/redirect/)
  })
})
