import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { CsvImportWizard } from './components/csv-import/csv-import-wizard'

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
  'employee_code,first_name,middle_name,last_name,email,birthdate,gender,civil_status',
  'EMP001,John,D.,Doe,john@example.com,1990-01-01,Male,Single',
  'EMP002,Jane,M.,Roe,jane@example.com,1985-05-15,Female,Married',
].join('\n')

describe('CSV import retry / resume (§8.11)', () => {
  it('continues past a failed row, reports partial results, and uses the error toast', async () => {
    // Row 1 succeeds; row 2 fails with a server error.
    apiPostMock.mockResolvedValueOnce({ data: {} })
    apiPostMock.mockRejectedValueOnce({ response: { status: 500, data: { message: 'boom' } } })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <CsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 2 Employees$/i }))

    // Both rows are attempted (no early abort).
    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(2)
      expect(apiPostMock).toHaveBeenNthCalledWith(1, '/employees', expect.objectContaining({ employee_code: 'EMP001' }))
      expect(apiPostMock).toHaveBeenNthCalledWith(2, '/employees', expect.objectContaining({ employee_code: 'EMP002' }))
    })

    // Partial results surfaced.
    await expect.element(getByText(/1 succeeded/)).toBeInTheDocument()
    await expect.element(getByText(/1 failed/)).toBeInTheDocument()

    // Error toast (not success) for the partial-failure path.
    expect(toastErrorMock).toHaveBeenCalledWith('Imported 1 employees, 1 failed')
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })
})
