import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { CsvImportWizard } from './components/csv-import/csv-import-wizard'

const { apiPostMock, toastErrorMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(), toastErrorMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({ api: { post: (...a: unknown[]) => apiPostMock(...a) } }))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: (...a: unknown[]) => toastErrorMock(...a) },
}))

const CSV = [
  'employee_code,first_name,middle_name,last_name,email,birthdate,gender,civil_status',
  'EMP099,Zed,Q.,Fail,zed@example.com,1990-01-01,Male,Single',
].join('\n')

// Harness owns `open` + a `key`. Bumping the key mounts a fresh Wizard
// (clean slate) — simulating a resumed flow after the prior session closed.
function WizardHarness() {
  const [open, setOpen] = useState(false)
  const [key, setKey] = useState(0)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Launch wizard</button>
      <button type="button" onClick={() => { setKey((k) => k + 1); setOpen(true) }}>Reopen wizard</button>
      <CsvImportWizard key={key} open={open} onOpenChange={setOpen} />
    </>
  )
}

describe('CSV wizard resume / clean slate on reopen (§8.13)', () => {
  it('resets to an empty, unimported state after close + reopen', async () => {
    apiPostMock.mockRejectedValue({ response: { status: 500, data: { message: 'boom' } } })

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(<WizardHarness />)

    // Phase 1: open -> paste -> import -> error path produces a result.
    await userEvent.click(getByRole('button', { name: 'Launch wizard' }))
    await expect.element(getByRole('heading', { name: /Import Employees from CSV/i })).toBeInTheDocument()

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(getByRole('button', { name: /^Import 1 Employees$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
    await expect.element(getByText(/1 failed/)).toBeInTheDocument()

    // Phase 2: close the wizard (Escape -> onOpenChange(false)). The wizard
    // resets its internal state after its 200ms teardown.
    await userEvent.keyboard('{Escape}')
    await vi.waitFor(() => {
      expect(getByRole('heading', { name: /Import Employees from CSV/i })).not.toBeInTheDocument()
    })
    await expect.element(getByText('1 failed')).not.toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 250)) // wait past the 200ms internal reset

    // Phase 3: reopen -> a fresh instance must show 0 rows / no stale results.
    await userEvent.click(getByRole('button', { name: 'Reopen wizard' }))
    await expect.element(getByRole('button', { name: /^Import 0 Employees$/i })).toBeInTheDocument()
    await expect.element(getByText('1 failed')).not.toBeInTheDocument()
  })
})
