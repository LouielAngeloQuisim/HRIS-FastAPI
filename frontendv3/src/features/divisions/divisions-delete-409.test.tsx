import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import DivisionPage from './index'

const { useDivisionsMock, useCanMock, apiDeleteMock, toastErrorMock } = vi.hoisted(() => ({
  useDivisionsMock: vi.fn(),
  useCanMock: vi.fn(),
  apiDeleteMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))
vi.mock('@/lib/api/divisions', () => ({
  useDivisions: (...a: unknown[]) => useDivisionsMock(...a),
  useCreateDivision: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateDivision: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteDivision: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('@/context/permissions-provider', () => ({ useCan: (...a: unknown[]) => useCanMock(...a) }))
vi.mock('@/lib/api/client', () => ({ api: { delete: (...a: unknown[]) => apiDeleteMock(...a) } }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: (...a: unknown[]) => toastErrorMock(...a) } }))

const DIVS = {
  data: [{ id: 'div-1', code: 'D-01', name: 'North', description: 'd', director_id: 'u1' }],
  count: 1,
}

// §8.7 — Division delete 409 with active Departments.
//
// The current divisions ResourceDeleteDialog.onError shows a *generic*
// toast ("Failed to delete Division") and ignores the 409 ErrorBody.
// It does NOT surface the specific "still has active departments" copy
// required by §5. This test therefore asserts the verifiably-achievable
// contract: (1) row stays (no optimistic delete), (2) correct endpoint
// hit, (3) conflict is surfaced via *some* error toast (not silent).
// The §5 specific-message surfacing is a documented feature gap (see report)
// — asserting it against the current component would fail.
describe('Division delete 409 conflict (§8.7)', () => {
  it('shows a toast and keeps the row when the server returns 409 with active depts', async () => {
    useDivisionsMock.mockReturnValue({ data: DIVS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)
    apiDeleteMock.mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: { type: 'conflict', message: 'still has active departments', details: [] },
          request_id: 'req-8.7',
        },
      },
    })

    const { getByRole, getByText } = await renderWithClient(<DivisionPage />)
    await expect.element(getByText('D-01')).toBeInTheDocument()

    // Open the confirm dialog.
    const deleteButtons = getByRole('button', { name: /Delete/i }).all()
    await userEvent.click(deleteButtons[0])
    await expect.element(getByRole('button', { name: /^Delete$/i })).toBeInTheDocument()

    await userEvent.click(getByRole('button', { name: /^Delete$/i }))

    // Correct endpoint hit.
    await vi.waitFor(() => { expect(apiDeleteMock).toHaveBeenCalledWith('/divisions/div-1') })

    // Conflict surfaced with the SPECIFIC backend message (errors.data.error.message),
    // not a generic 'Failed to delete Division' — this fails against the old onError.
    await vi.waitFor(() => { expect(toastErrorMock).toHaveBeenCalledWith('still has active departments') })

    // Row NOT removed — no optimistic delete, no silent removal.
    await expect.element(getByText('D-01')).toBeInTheDocument()
  })
})
