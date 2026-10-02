vi.mock('@/lib/api/leave-policies', () => ({ useLeavePolicies: () => ({ data: { data: [{ id: 'policy-1', code: 'VL', name: 'Vacation', is_active: true }] } }) }))
vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [{ id: 'emp-1', employee_code: 'EMP1', first_name: 'Test', last_name: 'Employee' }] }, isPending: false }) }))
import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
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

describe('LeaveLedgerPage (year filter)', () => {
  it('calls refetch when refresh button is clicked', async () => {
    refetch.mockClear()
    useLeaveLedgerMock.mockReturnValue({
      data: { data: [], summary: { granted_total: 0, consumed_total: 0, remaining: 0 } },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveLedgerPage />)
    if (document.querySelector('#leave-ledger-employee')) {
      await userEvent.selectOptions(document.querySelector('#leave-ledger-employee')!, 'emp-1')
      await userEvent.selectOptions(document.querySelector('#leave-ledger-policy')!, 'policy-1')
    }
    const refreshButton = screen.getByRole('button', { name: /refresh/i })
    await userEvent.click(refreshButton)
    expect(refetch).toHaveBeenCalled()
  })
})
