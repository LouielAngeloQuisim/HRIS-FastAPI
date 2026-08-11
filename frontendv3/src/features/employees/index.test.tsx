import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { Employees } from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

// Permissions gate passes.
vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

// Default: error state. Each test overrides via useEmployeesMock.
const { useEmployeesMock } = vi.hoisted(() => ({ useEmployeesMock: vi.fn() }))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: (...args: unknown[]) => useEmployeesMock(...args),
}))

// Isolate the page from the header/sidebar chrome.
vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))
vi.mock('./components/employees-table', () => ({
  EmployeesTable: () => <div>No employees found.</div>,
}))

function text(screen: { container: HTMLElement }): string {
  return screen.container.textContent ?? ''
}

describe('Employees (error handling)', () => {
  it('renders an error state (not the empty-table UI) when the query fails', async () => {
    useEmployeesMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<Employees />)

    // Error UI present, empty-table UI absent.
    expect(text(screen)).toContain('Failed to load employees.')
    expect(text(screen)).not.toContain('No employees found.')
  })

  it('calls refetch when retry is clicked', async () => {
    refetch.mockClear()
    useEmployeesMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<Employees />)

    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('keeps the loading state for a pending query', async () => {
    useEmployeesMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      refetch,
    })

    const screen = await render(<Employees />)

    expect(text(screen)).toContain('Loading employees…')
  })
})
