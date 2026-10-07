import { beforeEach, describe, expect, it, vi } from 'vitest'
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

const DUPLICATE_DAY_CSV = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T12:00:00Z,DAY',
  'EMP001,2026-08-04T13:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')

describe('Attendance CSV import basic (§8.10)', () => {
  beforeEach(() => {
    apiPostMock.mockReset()
    toastSuccessMock.mockReset()
    toastErrorMock.mockReset()
  })

  it('preflights and commits the complete attendance batch atomically', async () => {
    apiPostMock
      .mockResolvedValueOnce({ data: { valid: true, issues: [], excluded: [] } })
      .mockResolvedValueOnce({ data: { created_count: 2, excluded_count: 0, records: [] } })

    const { client, getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    const invalidation = vi.spyOn(client, 'invalidateQueries')
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))

    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(2)
      expect(apiPostMock).toHaveBeenNthCalledWith(1, '/daily-time-records/import-batches/preflight', expect.objectContaining({
        batch_id: expect.any(String),
        rows: expect.arrayContaining([expect.objectContaining({ employee_code: 'EMP001' }), expect.objectContaining({ employee_code: 'EMP002' })]),
      }))
      expect(apiPostMock).toHaveBeenNthCalledWith(2, '/daily-time-records/import-batches/commit', expect.any(Object))
    })

    await expect.element(getByText(/2 succeeded/)).toBeInTheDocument()
    expect(toastSuccessMock).toHaveBeenCalledWith(expect.stringContaining('Attendance batch saved. 2 new'))
    expect(toastErrorMock).not.toHaveBeenCalled()
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['daily-time-records'] })
  })

  it('requires an explicit merge and saves repeated employee/date rows as separate intervals', async () => {
    apiPostMock
      .mockResolvedValueOnce({ data: { valid: false, issues: [
        { row_index: 0, code: 'duplicate_employee_work_date', work_date: '2026-08-04', employee_code: 'EMP001', message: 'Duplicate date.' },
        { row_index: 1, code: 'duplicate_employee_work_date', work_date: '2026-08-04', employee_code: 'EMP001', message: 'Duplicate date.' },
      ], excluded: [] } })
      .mockResolvedValueOnce({ data: { valid: true, issues: [], excluded: [] } })
      .mockResolvedValueOnce({ data: { created_count: 1, excluded_count: 0, records: [] } })

    const screen = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await userEvent.fill(screen.getByPlaceholder(/employee_code/), DUPLICATE_DAY_CSV)
    await userEvent.click(screen.getByRole('button', { name: /^Import 2 Records$/i }))
    await expect.element(screen.getByTestId('merge-duplicate-date-2')).toBeVisible()
    await userEvent.click(screen.getByTestId('merge-duplicate-date-2'))
    await userEvent.click(screen.getByRole('button', { name: /^Import 1 Records$/i }))

    await vi.waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(3))
    const committedRequest = apiPostMock.mock.calls[2][1] as { rows: Array<{ intervals: Array<{ start_at: string; end_at: string; original_row: Record<string, string> }> }> }
    expect(committedRequest.rows).toHaveLength(1)
    expect(committedRequest.rows[0].intervals).toHaveLength(2)
    expect(committedRequest.rows[0].intervals[0].original_row.login_date).toBe('2026-08-04T08:00:00Z')
    expect(committedRequest.rows[0].intervals[1].original_row.login_date).toBe('2026-08-04T13:00:00Z')
    await expect.element(screen.getByText(/1 succeeded/)).toBeInTheDocument()
  })
})
