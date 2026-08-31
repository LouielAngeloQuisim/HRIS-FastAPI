import { renderWithClient } from '@/test-utils/providers'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import LotsPage from './index'

const { useLotsMock, useCanMock, apiDeleteMock, toastErrorMock } = vi.hoisted(
  () => ({
    useLotsMock: vi.fn(),
    useCanMock: vi.fn(),
    apiDeleteMock: vi.fn(),
    toastErrorMock: vi.fn(),
  })
)
vi.mock('@/lib/api/lots', () => ({
  useLots: (...a: unknown[]) => useLotsMock(...a),
  useCreateLot: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateLot: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteLot: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe('Lots delete 409 conflict (§8.8)', () => {
  it('keeps the row and surfaces the specific backend message on 409', async () => {
    useLotsMock.mockReturnValue({
      data: {
        data: [{ id: 'l1', lot_num: 5, lot_name: 'Lot 5', blocks_id: 'b1' }],
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
          error: { type: 'conflict', message: 'still has active blocks' },
          request_id: 'req-8.8-lots',
        },
      },
    })

    const { getByRole, getByText } = await renderWithClient(<LotsPage />)
    await expect.element(getByText('Lot 5')).toBeInTheDocument()

    await userEvent.click(getByRole('button', { name: /Delete/i }).all()[0])
    await expect
      .element(getByRole('button', { name: /^Delete$/i }))
      .toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /^Delete$/i }))

    await vi.waitFor(() => {
      expect(apiDeleteMock).toHaveBeenCalledWith('/lots/l1')
    })
    // SPECIFIC backend 409 message surfaced via extractDeleteErrorMessage (not generic "Failed to delete Lot").
    await vi.waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('still has active blocks')
    })
    await expect.element(getByText('Lot 5')).toBeInTheDocument()
  })
})
