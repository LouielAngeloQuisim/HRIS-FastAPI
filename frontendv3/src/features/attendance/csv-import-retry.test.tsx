import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { AttendanceCsvImportWizard } from './components/csv-import/attendance-csv-wizard'

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))

const { apiPostMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({
  api: { post: (...a: unknown[]) => apiPostMock(...a) },
  // auth-store hydrate() reads these at import time; no session in this test.
  getAccessToken: () => undefined,
  getRefreshToken: () => undefined,
  clearTokens: () => {},
}))
vi.mock('sonner', () => ({
  toast: { success: (...a: unknown[]) => toastSuccessMock(...a), error: (...a: unknown[]) => toastErrorMock(...a) },
}))

const CSV = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
  'EMP002,2026-08-04T09:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')

describe('Attendance CSV import retry (§8.11)', () => {
  it('blocks the complete batch when preflight finds one invalid row', async () => {
    apiPostMock.mockResolvedValueOnce({
      data: {
        valid: false,
        issues: [{ row_index: 1, employee_code: 'EMP002', code: 'attendance_invalid', message: 'Missing shift assignment' }],
        excluded: [],
      },
    })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))

    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(1)
      expect(apiPostMock).toHaveBeenCalledWith('/daily-time-records/import-batches/preflight', expect.any(Object))
    })

    await expect.element(getByText(/0 succeeded/)).toBeInTheDocument()
    await expect.element(getByText(/2 failed/)).toBeInTheDocument()
    expect(toastErrorMock).toHaveBeenCalledWith('Attendance needs correction in 1 row(s). Nothing was saved.')
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })
})
