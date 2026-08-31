import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { PermissionMatrix } from './permission-matrix'

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
const { apiPatchMock } = vi.hoisted(() => ({ apiPatchMock: vi.fn() }))
const { apiGetMock } = vi.hoisted(() => ({ apiGetMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))
vi.mock('@/lib/api/client', () => ({
  api: {
    patch: (...args: unknown[]) => apiPatchMock(...args),
    get: (...args: unknown[]) => apiGetMock(...args),
  },
}))

describe('RBAC PermissionMatrix editor (§8.4 — mocked useCan)', () => {
  it('shows the Save control and enables checkboxes when canEdit (administration/edit) is true', async () => {
    useCanMock.mockReturnValue(true)
    apiPatchMock.mockResolvedValue({ data: {} })
    apiGetMock.mockResolvedValue({ data: { permissions: [] } })

    const { getByRole } = await renderWithClient(
      <PermissionMatrix open={true} roleId="r1" roleName="Manager" onClose={vi.fn()} />
    )

    await expect.element(getByRole('button', { name: /Save Permissions/i })).toBeInTheDocument()

    const divisionView = getByRole('checkbox', { name: 'view' }).all()[0]
    await expect.element(divisionView).toBeEnabled()
  })

  it('hides Save and disables checkboxes when canEdit is false', async () => {
    useCanMock.mockReturnValue(false)
    apiPatchMock.mockResolvedValue({ data: {} })
    apiGetMock.mockResolvedValue({ data: { permissions: [] } })

    const { getByRole } = await renderWithClient(
      <PermissionMatrix open={true} roleId="r1" roleName="Manager" onClose={vi.fn()} />
    )

    await expect
      .element(getByRole('button', { name: /Save Permissions/i }))
      .not.toBeInTheDocument()

    const divisionView = getByRole('checkbox', { name: 'view' }).all()[0]
    await expect.element(divisionView).toBeDisabled()
  })

  it('toggles a permission and persists via PATCH when saved', async () => {
    useCanMock.mockReturnValue(true)
    apiPatchMock.mockResolvedValue({ data: {} })
    apiGetMock.mockResolvedValue({ data: { permissions: [] } })

    const onClose = vi.fn()
    const { getByRole } = await renderWithClient(
      <PermissionMatrix open={true} roleId="r1" roleName="Manager" onClose={onClose} />
    )

    const divisionView = getByRole('checkbox', { name: 'view' }).all()[0]
    await userEvent.click(divisionView)

    await userEvent.click(getByRole('button', { name: /Save Permissions/i }))

    await vi.waitFor(() => {
      expect(apiPatchMock).toHaveBeenCalledWith('/rbac/roles/r1', {
        permissions: expect.arrayContaining(['division.view']),
      })
    })
  })

  it('renders inside a dialog with a close button', async () => {
    useCanMock.mockReturnValue(true)
    apiPatchMock.mockResolvedValue({ data: {} })
    apiGetMock.mockResolvedValue({ data: { permissions: [] } })

    const onClose = vi.fn()
    const { getByRole } = await renderWithClient(
      <PermissionMatrix open={true} roleId="r1" roleName="Manager" onClose={onClose} />
    )

    const closeButton = getByRole('button', { name: /close/i })
    await userEvent.click(closeButton)

    expect(onClose).toHaveBeenCalled()
  })
})
