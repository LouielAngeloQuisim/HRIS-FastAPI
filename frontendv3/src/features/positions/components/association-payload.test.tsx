import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/positions', () => ({ useCreatePosition: () => ({ mutateAsync }), useUpdatePosition: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/departments', () => ({ useDepartments: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
it('sends the selected parent IDs and backend field names', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('position-code-input'), 'P')
  await userEvent.type(screen.getByTestId('position-title-input'), 'Position')
  await userEvent.click(screen.getByTestId('position-department-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('position-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"code": "P", "title": "Position", "department_id": "parent"}))
  expect(onClose).toHaveBeenCalledOnce()
})
