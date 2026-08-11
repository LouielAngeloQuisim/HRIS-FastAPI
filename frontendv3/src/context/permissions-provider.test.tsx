import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render } from 'vitest-browser-react'
import { PermissionsProvider, useCan, useRoleCode } from '@/context/permissions-provider'
import { type MyPermissions } from '@/lib/api/types'

const mockUseQuery = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}))

function TestComponent({
  permissions: _permissions,
}: {
  permissions: MyPermissions | null
}) {
  return (
    <>
      <span data-testid="super">{useCan('payroll', 'add') ? 'yes' : 'no'}</span>
      <span data-testid="view">{useCan('emp_list', 'view') ? 'yes' : 'no'}</span>
      <span data-testid="edit">{useCan('emp_list', 'edit') ? 'yes' : 'no'}</span>
      <span data-testid="missing">{useCan('payroll', 'view') ? 'yes' : 'no'}</span>
      <span data-testid="role">{useRoleCode() ?? 'none'}</span>
    </>
  )
}

describe('useCan / useRoleCode', () => {
  const surPerms: MyPermissions = {
    role_code: 'SUR',
    is_superuser: false,
    permissions: {
      emp_list: { view: true, add: false, edit: false, delete: false },
      humanres: { view: true, add: false, edit: false, delete: false },
    },
  }

  beforeEach(() => {
    mockUseQuery.mockReturnValue({ data: null })
  })

  it('returns false/denied when permissions context is null', async () => {
    const screen = await render(
      <PermissionsProvider enabled={true}>
        <TestComponent permissions={null} />
      </PermissionsProvider>
    )
    await expect.element(screen.getByTestId('super')).toHaveTextContent('no')
    await expect.element(screen.getByTestId('view')).toHaveTextContent('no')
    await expect.element(screen.getByTestId('role')).toHaveTextContent('none')
  })

  it('superuser bypasses all checks', async () => {
    mockUseQuery.mockReturnValue({
      data: { ...surPerms, is_superuser: true, permissions: {} },
    })
    const screen = await render(
      <PermissionsProvider enabled={true}>
        <TestComponent permissions={null} />
      </PermissionsProvider>
    )
    await expect.element(screen.getByTestId('super')).toHaveTextContent('yes')
    await expect.element(screen.getByTestId('missing')).toHaveTextContent('yes')
  })

  it('reads view/edit from the permissions map', async () => {
    mockUseQuery.mockReturnValue({ data: surPerms })
    const screen = await render(
      <PermissionsProvider enabled={true}>
        <TestComponent permissions={null} />
      </PermissionsProvider>
    )
    await expect.element(screen.getByTestId('view')).toHaveTextContent('yes')
    await expect.element(screen.getByTestId('edit')).toHaveTextContent('no')
  })

  it('denies by default when module is absent', async () => {
    mockUseQuery.mockReturnValue({ data: surPerms })
    const screen = await render(
      <PermissionsProvider enabled={true}>
        <TestComponent permissions={null} />
      </PermissionsProvider>
    )
    await expect.element(screen.getByTestId('missing')).toHaveTextContent('no')
  })

  it('returns role_code via useRoleCode', async () => {
    mockUseQuery.mockReturnValue({ data: surPerms })
    const screen = await render(
      <PermissionsProvider enabled={true}>
        <TestComponent permissions={null} />
      </PermissionsProvider>
    )
    await expect.element(screen.getByTestId('role')).toHaveTextContent('SUR')
  })

  it('does not throw while permissions query is still loading (data undefined)', async () => {
    mockUseQuery.mockReturnValue({ data: undefined })
    const screen = await render(
      <PermissionsProvider enabled={true}>
        <TestComponent permissions={null} />
      </PermissionsProvider>
    )
    await expect.element(screen.getByTestId('super')).toHaveTextContent('no')
    await expect.element(screen.getByTestId('view')).toHaveTextContent('no')
    await expect.element(screen.getByTestId('edit')).toHaveTextContent('no')
    await expect.element(screen.getByTestId('missing')).toHaveTextContent('no')
    await expect.element(screen.getByTestId('role')).toHaveTextContent('none')
  })
})
