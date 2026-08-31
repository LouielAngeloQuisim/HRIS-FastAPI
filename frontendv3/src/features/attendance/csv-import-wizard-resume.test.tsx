import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { AttendanceCsvImportWizard } from './components/csv-import/attendance-csv-wizard'

const { apiPostMock, toastErrorMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(), toastErrorMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({ api: { post: (...a: unknown[]) => apiPostMock(...a) } }))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: (...a: unknown[]) => toastErrorMock(...a) },
}))

const CSV = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP099,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')

function WizardHarness() {
  const [open, setOpen] = useState(false)
  const [key, setKey] = useState(0)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Launch wizard</button>
      <button type="button" onClick={() => { setKey((k) => k + 1); setOpen(true) }}>Reopen wizard</button>
      <AttendanceCsvImportWizard key={key} open={open} onOpenChange={setOpen} />
    </>
  )
}

describe('Attendance CSV wizard resume / clean slate on reopen (§8.13)', () => {
  it('resets to an empty, unimported state after close + reopen', async () => {
    apiPostMock.mockRejectedValue({ response: { status: 500, data: { message: 'boom' } } })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(<WizardHarness />)

    await userEvent.click(getByRole('button', { name: 'Launch wizard' }))
    await expect.element(getByRole('heading', { name: /Import Attendance from CSV/i })).toBeInTheDocument()

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
    await expect.element(getByText(/1 failed/)).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    await vi.waitFor(() => {
      expect(getByRole('heading', { name: /Import Attendance from CSV/i })).not.toBeInTheDocument()
    })
    await expect.element(getByText('1 failed')).not.toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 250))

    await userEvent.click(getByRole('button', { name: 'Reopen wizard' }))
    await expect.element(getByRole('button', { name: /^Import 0 Records$/i })).toBeInTheDocument()
    await expect.element(getByText('1 failed')).not.toBeInTheDocument()
  })
})
