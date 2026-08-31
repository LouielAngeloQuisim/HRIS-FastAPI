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

describe('Attendance CSV import basic (§8.10)', () => {
  it('imports 2 valid rows with zero errors, posts each, and toasts success', async () => {
    apiPostMock.mockResolvedValue({ data: {} })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))

    // One POST /daily-time-records per row, in order.
    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(2)
      expect(apiPostMock).toHaveBeenCalledWith('/daily-time-records', expect.objectContaining({ employee_code: 'EMP001' }))
      expect(apiPostMock).toHaveBeenLastCalledWith('/daily-time-records', expect.objectContaining({ employee_code: 'EMP002' }))
    })

    await expect.element(getByText(/2 succeeded/)).toBeInTheDocument()
    expect(toastSuccessMock).toHaveBeenCalledWith('Successfully imported 2 time records')
    expect(toastErrorMock).not.toHaveBeenCalled()
  })
})
