import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/projects', () => ({ useCreateProject: () => ({ mutateAsync }), useUpdateProject: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/subdivisions', () => ({ useSubdivisions: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
vi.mock('@/lib/api/project-types', () => ({ useProjectTypes: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
it('sends the selected parent IDs and backend field names', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('project-code-input'), 'P')
  await userEvent.type(screen.getByTestId('project-name-input'), 'Project')
  await userEvent.click(screen.getByTestId('project-subdivision-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('project-type-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('project-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"code": "P", "name": "Project", "subdivision_id": "parent", "project_type_id": "parent"}))
  expect(onClose).toHaveBeenCalledOnce()
})
