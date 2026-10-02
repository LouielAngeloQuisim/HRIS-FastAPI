import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/blocks', () => ({ useCreateBlock: () => ({ mutateAsync }), useUpdateBlock: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/phases', () => ({ usePhases: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
it('sends the selected parent IDs and backend field names', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('blocks-name-input'), 'Block')
  await userEvent.click(screen.getByTestId('blocks-phase-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('blocks-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"block_name": "Block", "phase_id": "parent"}))
  expect(onClose).toHaveBeenCalledOnce()
})
