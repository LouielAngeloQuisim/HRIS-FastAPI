import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/departments', () => ({ useCreateDepartment: () => ({ mutateAsync }), useUpdateDepartment: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/divisions', () => ({ useDivisions: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
it('sends the selected parent IDs and backend field names', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('department-code-input'), 'D')
  await userEvent.type(screen.getByTestId('department-name-input'), 'Department')
  await userEvent.click(screen.getByTestId('department-division-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('department-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"code": "D", "name": "Department", "division_id": "parent"}))
  expect(onClose).toHaveBeenCalledOnce()
})
