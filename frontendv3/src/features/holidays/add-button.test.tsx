import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import HolidaysPage from './index'

vi.mock('./components/resource-form', () => ({
  ResourceForm: () => null,
}))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: (_module: string, action: string) => action === 'view',
}))

const { useHolidayConfigsMock } = vi.hoisted(() => ({
  useHolidayConfigsMock: vi.fn(),
}))
vi.mock('@/lib/api/holidays', () => ({
  useHolidayConfigs: (...args: unknown[]) => useHolidayConfigsMock(...args),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('HolidaysPage (add button)', () => {
  it('hides Add button when user lacks add permission', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const { container } = await render(<HolidaysPage />)
    const addButtons = container.querySelectorAll('button')
    expect([...addButtons].some(btn => btn.textContent === 'Add Holiday')).toBe(false)
  })
})
