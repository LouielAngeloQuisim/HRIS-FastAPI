import { beforeEach, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { save } = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock('@/lib/api/lots', () => ({ useCreateLot: () => ({ mutateAsync: save }), useUpdateLot: () => ({ mutateAsync: save }) }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: () => ({ data: { data: [{ id: 'block-1', block_name: 'Block' }] }, isPending: false }) }))
beforeEach(() => { save.mockReset().mockResolvedValue({}) })
it('preserves separate lot name and numeric number on edit', async () => {
 const screen = await render(<ResourceForm open onClose={vi.fn()} item={{ id: 'lot-1', blocks_id: 'block-1', lot_name: 'Original', lot_num: 101, category_id: null, is_deleted: false, created_at: '2026-10-02T00:00:00Z' }} />)
 await userEvent.fill(screen.getByLabelText('Lot Name', { exact: true }), 'Reviewed')
 await userEvent.click(screen.getByRole('button', { name: 'Update', exact: true }))
 expect(save).toHaveBeenCalledWith({ id: 'lot-1', data: { lot_name: 'Reviewed', lot_num: 101, blocks_id: 'block-1' } })
})
it('rejects fractional lot numbers before saving', async () => {
 const screen = await render(<ResourceForm open onClose={vi.fn()} item={{ id: 'lot-1', blocks_id: 'block-1', lot_name: 'Original', lot_num: 101, category_id: null, is_deleted: false, created_at: '2026-10-02T00:00:00Z' }} />)
 await userEvent.fill(screen.getByLabelText('Lot Number', { exact: true }), '1.5')
 await userEvent.click(screen.getByRole('button', { name: 'Update', exact: true }))
 await expect.element(screen.getByText('Enter a whole lot number')).toBeVisible()
 expect(save).not.toHaveBeenCalled()
})
