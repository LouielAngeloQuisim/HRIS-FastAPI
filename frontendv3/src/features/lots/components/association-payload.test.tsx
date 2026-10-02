import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/lots', () => ({ useCreateLot: () => ({ mutateAsync }), useUpdateLot: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
it('sends the selected parent IDs and backend field names', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('lots-lot-number-input'), 'Lot 1')
  await userEvent.click(screen.getByTestId('lots-block-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('lots-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"lot_name": "Lot 1", "blocks_id": "parent"}))
  expect(onClose).toHaveBeenCalledOnce()
})
