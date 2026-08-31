import { renderWithClient } from '@/test-utils/providers'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import BlocksPage from './index'

const { useBlocksMock, useCanMock, apiDeleteMock, toastErrorMock } = vi.hoisted(
  () => ({
    useBlocksMock: vi.fn(),
    useCanMock: vi.fn(),
    apiDeleteMock: vi.fn(),
    toastErrorMock: vi.fn(),
  })
)
vi.mock('@/lib/api/blocks', () => ({
  useBlocks: (...a: unknown[]) => useBlocksMock(...a),
  useCreateBlock: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateBlock: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteBlock: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...a: unknown[]) => useCanMock(...a),
}))
vi.mock('@/lib/api/client', () => ({
  api: { delete: (...a: unknown[]) => apiDeleteMock(...a) },
}))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: (...a: unknown[]) => toastErrorMock(...a) },
}))

describe('Blocks delete 409 conflict (§8.8)', () => {
  it('keeps the row and surfaces the specific backend message on 409', async () => {
    useBlocksMock.mockReturnValue({
      data: {
        data: [{ id: 'b1', block_name: 'Block A', phase_id: 'p1' }],
        count: 1,
      },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)
    apiDeleteMock.mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: { type: 'conflict', message: 'still has active phases' },
          request_id: 'req-8.8-blocks',
        },
      },
    })

    const { getByRole, getByText } = await renderWithClient(<BlocksPage />)
    await expect.element(getByText('Block A')).toBeInTheDocument()

    await userEvent.click(getByRole('button', { name: /Delete/i }).all()[0])
    await expect
      .element(getByRole('button', { name: /^Delete$/i }))
      .toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /^Delete$/i }))

    await vi.waitFor(() => {
      expect(apiDeleteMock).toHaveBeenCalledWith('/blocks/b1')
    })
    // SPECIFIC backend 409 message surfaced via extractDeleteErrorMessage (not generic "Failed to delete Block").
    await vi.waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('still has active phases')
    })
    await expect.element(getByText('Block A')).toBeInTheDocument()
  })
})
