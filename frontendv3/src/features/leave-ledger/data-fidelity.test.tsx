import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import LeaveLedgerPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useLeaveLedgerMock } = vi.hoisted(() => ({ useLeaveLedgerMock: vi.fn() }))
vi.mock('@/lib/api/leave-ledger', () => ({
  useLeaveLedger: (...args: unknown[]) => useLeaveLedgerMock(...args),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('LeaveLedgerPage (data fidelity)', () => {
  it('renders summary numbers unmodified from API', async () => {
    useLeaveLedgerMock.mockReturnValue({
      data: {
        data: [],
        summary: { granted_total: 12.5, consumed_total: 3.25, remaining: 9.25 },
      },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveLedgerPage />)
    await expect.element(screen.getByText('Granted: 12.5 | Consumed: 3.25 | Remaining: 9.25')).toBeVisible()
  })

  it('renders empty state when no ledger entries', async () => {
    useLeaveLedgerMock.mockReturnValue({
      data: { data: [], summary: { granted_total: 0, consumed_total: 0, remaining: 0 } },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveLedgerPage />)
    await expect.element(screen.getByText('No ledger entries found.')).toBeVisible()
  })
})
