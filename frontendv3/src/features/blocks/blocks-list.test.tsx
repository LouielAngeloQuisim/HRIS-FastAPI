import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import BlocksPage from './index'

vi.mock('./components/resource-form', () => ({ ResourceForm: () => null }))
vi.mock('./components/resource-delete-dialog', () => ({ ResourceDeleteDialog: () => null }))

const { useBlocksMock } = vi.hoisted(() => ({ useBlocksMock: vi.fn() }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: (...args: unknown[]) => useBlocksMock(...args) }))
const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({ useCan: (...args: unknown[]) => useCanMock(...args) }))

const BLOCKS = {
  data: [{ id: 'b1', block_name: 'Block A', phase_id: 'p1' }],
  count: 1,
}

describe('Blocks list (§8.6 permission gate)', () => {
  it('renders rows bound to useBlocks data', async () => {
    useBlocksMock.mockReturnValue({ data: BLOCKS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)
    const { getByText } = await render(<BlocksPage />)
    await expect.element(getByText('Block A')).toBeInTheDocument()
  })

  it('hides the Add button when create permission is denied', async () => {
    useBlocksMock.mockReturnValue({ data: BLOCKS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockImplementation((_m: string, action: string) => action === 'view')
    const denied = await render(<BlocksPage />)
    await expect.element(denied.getByRole('button', { name: /Add Block/i })).not.toBeInTheDocument()

    useCanMock.mockReturnValue(true)
    const allowed = await render(<BlocksPage />)
    await expect.element(allowed.getByRole('button', { name: /Add Block/i })).toBeInTheDocument()
  })
})
