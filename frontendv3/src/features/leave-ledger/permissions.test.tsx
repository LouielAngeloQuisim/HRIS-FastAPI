import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { type useLeaveLedger } from '@/lib/api/leave-ledger'
import LeaveLedgerPage from './index'

describe('LeaveLedgerPage (permissions)', () => {
  it('denies access when user lacks view permission', async () => {
    vi.mock('@/context/permissions-provider', () => ({
      useCan: () => false,
    }))

    const { useLeaveLedgerMock } = vi.hoisted(() => ({ useLeaveLedgerMock: vi.fn((..._args: Parameters<typeof useLeaveLedger>) => ({ data: { data: [], summary: { granted_total: 0, consumed_total: 0, remaining: 0 } }, isPending: false, isError: false, refetch: vi.fn() })) }))
    vi.mock('@/lib/api/leave-ledger', () => ({
      useLeaveLedger: (...args: Parameters<typeof useLeaveLedger>) => useLeaveLedgerMock(...args),
    }))

    vi.mock('@/components/layout/header', () => ({
      Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
    }))
    vi.mock('@/components/search', () => ({ Search: () => null }))
    vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
    vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
    vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

    const screen = await render(<LeaveLedgerPage />)
    await expect.element(screen.getByText('You do not have permission to view leave ledger.')).toBeVisible()
  })
})
