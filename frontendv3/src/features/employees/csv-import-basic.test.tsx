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

describe('CSV import basic (§8.10)', () => {
  it('imports 2 valid rows with zero errors, posts each, and toasts success', async () => {
    apiPostMock.mockResolvedValue({ data: {} })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <CsvImportWizard open={true} onOpenChange={() => {}} />
    )

    // Paste CSV into the textarea (page-scoped, reaches the Dialog portal),
    // then trigger import.
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 2 Employees$/i }))

    // One POST /employees per row, in order.
    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(2)
      expect(apiPostMock).toHaveBeenCalledWith('/employees', expect.objectContaining({ employee_code: 'EMP001' }))
      expect(apiPostMock).toHaveBeenLastCalledWith('/employees', expect.objectContaining({ employee_code: 'EMP002' }))
    })

    // Results table reports 2 succeeded, none failed.
    await expect.element(getByText(/2 succeeded/)).toBeInTheDocument()
    // Success toast surfaced.
    expect(toastSuccessMock).toHaveBeenCalledWith('Successfully imported 2 employees')
    // No error toast.
    expect(toastErrorMock).not.toHaveBeenCalled()
  })
})
