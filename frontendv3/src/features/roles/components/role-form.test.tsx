import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { RoleForm } from './role-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/roles', () => ({
  useCreateRole: () => ({ mutateAsync }), useUpdateRole: () => ({ mutateAsync }),
}))
it('submits the required role code and name', async () => {
  const onClose = vi.fn()
  const screen = await render(<RoleForm role={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('role-code-input'), 'CUSTOM')
  await userEvent.type(screen.getByTestId('role-name-input'), 'Custom role')
  await userEvent.click(screen.getByTestId('role-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith({ code: 'CUSTOM', name: 'Custom role' })
  expect(onClose).toHaveBeenCalledOnce()
})

it('keeps an existing role code immutable while editing its name', async () => {
  const role = { id: 'custom', code: 'CUSTOM', name: 'Custom role', is_system: false, is_active: true, created_at: null }
  const screen = await render(<RoleForm role={role} open={true} onClose={() => {}} />)
  await expect.element(screen.getByTestId('role-code-input')).toBeDisabled()
  await expect.element(screen.getByTestId('role-code-input')).toHaveValue('CUSTOM')
  await expect.element(screen.getByTestId('role-name-input')).toBeEnabled()
})
