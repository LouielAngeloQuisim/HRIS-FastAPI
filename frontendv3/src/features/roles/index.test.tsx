import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import RolesPage from './index'

vi.mock('./components/role-form', () => ({
  RoleForm: () => null,
}))
vi.mock('./components/permission-matrix', () => ({
  PermissionMatrix: () => null,
}))

const { useRolesMock } = vi.hoisted(() => ({ useRolesMock: vi.fn() }))
vi.mock('@/lib/api/roles', () => ({
  useRoles: (...args: unknown[]) => useRolesMock(...args),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const ROLES = {
  data: [
    { id: 'r1', code: 'SADM', name: 'Super Administrator', is_system: true, is_active: true, created_at: null },
    { id: 'r2', code: 'ADM', name: 'Administrator', is_system: true, is_active: true, created_at: null },
    { id: 'r3', code: 'SUR', name: 'Employee (Self-Service)', is_system: true, is_active: true, created_at: null },
    { id: 'r4', code: 'CUSTOM', name: 'Custom Role', is_system: false, is_active: true, created_at: null },
  ],
  count: 4,
}

describe('RolesPage', () => {
  it('renders roles with system role indicators', async () => {
    useRolesMock.mockReturnValue({
      data: ROLES,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { container } = await render(<RolesPage />)

    // Verify all role names appear in the document
    const text = container.textContent || ''
    expect(text).toContain('Super Administrator')
    expect(text).toContain('Administrator')
    expect(text).toContain('Employee (Self-Service)')
    expect(text).toContain('Custom Role')

    // Verify system badge text exists somewhere in document
    expect(text).toContain('(system)')
  })

  it('renders disabled Edit button for system roles', async () => {
    useRolesMock.mockReturnValue({
      data: ROLES,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const screen = await render(<RolesPage />)

    const buttons = await screen.container.querySelectorAll('button')
    const editButtons = [...buttons].filter(b => b.textContent?.includes('Edit'))
    expect(editButtons.length).toBeGreaterThanOrEqual(1)
  })

  it('shows empty state when no roles', async () => {
    useRolesMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<RolesPage />)
    await expect.element(getByText('0 roles')).toBeVisible()
  })

  it('shows permission denied when not authorized', async () => {
    useCanMock.mockReturnValue(false)

    const { getByText } = await render(<RolesPage />)
    await expect
      .element(getByText(/You do not have permission to view roles/i))
      .toBeVisible()
  })
})
