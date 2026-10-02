import { expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { ResourceForm } from './resource-form'
const { save } = vi.hoisted(() => ({ save: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/models', () => ({ useCreateModel: () => ({ mutateAsync: save }), useUpdateModel: () => ({ mutateAsync: save }) }))
vi.mock('@/lib/api/model-types', () => ({ useModelTypes: () => ({ data: { data: [{ id: 'type-1', name: 'Residential' }] }, isPending: false }) }))
it('retains the selected model type and does not offer an unsupported description', async () => {
  const screen = await render(<ResourceForm item={null} open onClose={vi.fn()} />)
  await userEvent.fill(screen.getByLabelText('Name', { exact: true }), 'Model')
  await userEvent.click(screen.getByRole('combobox', { name: 'Model Type', exact: true }))
  await userEvent.click(screen.getByRole('option', { name: 'Residential', exact: true }))
  await expect.element(screen.getByLabelText('Description', { exact: true })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Create', exact: true }))
  await vi.waitFor(() => expect(save).toHaveBeenCalledExactlyOnceWith({ name: 'Model', model_type_id: 'type-1' }))
})
