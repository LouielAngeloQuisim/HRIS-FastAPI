import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { AttendanceCsvImportWizard } from './components/csv-import/attendance-csv-wizard'

const { apiPostMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({ api: { post: (...a: unknown[]) => apiPostMock(...a) } }))
vi.mock('sonner', () => ({
  toast: { success: (...a: unknown[]) => toastSuccessMock(...a), error: (...a: unknown[]) => toastErrorMock(...a) },
}))

const CSV = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
  'EMP002,2026-08-04T09:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')

describe('Attendance CSV import retry (§8.11)', () => {
  it('continues past a failed row, reports partial results, and uses the error toast', async () => {
    apiPostMock.mockResolvedValueOnce({ data: {} })
    apiPostMock.mockRejectedValueOnce({ response: { status: 500, data: { message: 'boom' } } })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))

    // Both rows are attempted (no early abort).
    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(2)
      expect(apiPostMock).toHaveBeenNthCalledWith(1, '/daily-time-records', expect.objectContaining({ employee_code: 'EMP001' }))
      expect(apiPostMock).toHaveBeenNthCalledWith(2, '/daily-time-records', expect.objectContaining({ employee_code: 'EMP002' }))
    })

    await expect.element(getByText(/1 succeeded/)).toBeInTheDocument()
    await expect.element(getByText(/1 failed/)).toBeInTheDocument()
    expect(toastErrorMock).toHaveBeenCalledWith('Imported 1 time records, 1 failed')
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })
})
