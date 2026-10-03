// PR74 review P1 regressions: the recoverable in-memory import batch is
// sensitive HR data (employee CSV + identity keys + verdicts) and must never
// cross an authenticated-account boundary. Covers: cross-account restore
// leak, logout mid-session invalidation, account change DURING a running
// import, and the QA-01 same-account recovery contract staying intact.
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { useAuthStore } from '@/stores/auth-store'
import { AttendanceCsvImportWizard, __resetRecoverableSlotForTests } from './components/csv-import/attendance-csv-wizard'

const { apiPostMock } = vi.hoisted(() => ({ apiPostMock: vi.fn() }))
vi.mock('@/lib/api/client', () => ({
  api: { post: (...a: unknown[]) => apiPostMock(...a) },
  // auth-store hydrate() reads these at import time; identity is driven here
  // through the REAL store actions (setUser / setAccessToken / reset).
  getAccessToken: () => undefined,
  getRefreshToken: () => undefined,
  clearTokens: () => {},
}))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const CSV = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')

function signIn(id: string) {
  useAuthStore.getState().auth.setUser({ id, email: `${id}@test.local`, fullName: `User ${id}`, isSuperuser: true, roleId: null, roleCode: 'admin' })
  useAuthStore.getState().auth.setAccessToken(`${id}-access-token`)
}

// Mirrors the real page mount (`{importOpen && <Wizard/>}`): closing
// UNMOUNTS the wizard, so only the module-level recoverable slot can
// preserve identities across reopen — that slot is what must not leak
// across accounts.
function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open wizard</button>
      {open && <AttendanceCsvImportWizard open={open} onOpenChange={setOpen} />}
    </>
  )
}

/** Import 1 row with an ambiguous 5xx (UNKNOWN), then close while unresolved. */
async function importUnresolvedAndClose(view: Awaited<ReturnType<typeof renderWithClient>>) {
  await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
  await userEvent.fill(view.getByPlaceholder(/employee_code/), CSV)
  await userEvent.click(view.getByRole('button', { name: /^Import 1 Records$/i }))
  await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
  await userEvent.click(view.getByTestId('csv-import-close-button'))
  await vi.waitFor(() => {
    expect(view.getByPlaceholder(/employee_code/)).not.toBeInTheDocument()
  })
}

beforeEach(() => {
  __resetRecoverableSlotForTests()
  useAuthStore.getState().auth.reset()
  apiPostMock.mockReset()
})

describe('Attendance CSV wizard account isolation (PR74 review P1)', () => {
  it('does not hand an unresolved batch to a different account on reopen', async () => {
    apiPostMock.mockRejectedValue({ response: { status: 502 } })
    signIn('user-aaaa')

    const view = await renderWithClient(<Harness />)
    await importUnresolvedAndClose(view)

    // Account switch (B logs in) while the batch sits unresolved: B's mount
    // must see a clean slate — no banner, no unknown rows.
    signIn('user-bbbb')
    await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
    await expect.element(view.getByTestId('csv-import-restored-banner')).not.toBeInTheDocument()
    await expect.element(view.getByTestId('csv-import-unknown-count')).not.toBeInTheDocument()
    await expect.element(view.getByRole('button', { name: /^Import 0 Records$/i })).toBeInTheDocument()
    await userEvent.click(view.getByTestId('csv-import-close-button'))
    await vi.waitFor(() => {
      expect(view.getByPlaceholder(/employee_code/)).not.toBeInTheDocument()
    })

    // Back as A: identity change INVALIDATED the batch — it is not silently
    // resurrected for a second session either (logout is destructive).
    signIn('user-aaaa')
    await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
    await expect.element(view.getByTestId('csv-import-restored-banner')).not.toBeInTheDocument()
    await expect.element(view.getByRole('button', { name: /^Import 0 Records$/i })).toBeInTheDocument()
  })

  it('drops a stored unresolved batch the moment the account logs out', async () => {
    apiPostMock.mockRejectedValue({ response: { status: 502 } })
    signIn('user-aaaa')

    const view = await renderWithClient(<Harness />)
    await importUnresolvedAndClose(view)

    // The SPA logout path calls auth.reset() (also what the store
    // subscription observes): slot dropped immediately.
    useAuthStore.getState().auth.reset()

    signIn('user-aaaa')
    await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
    await expect.element(view.getByTestId('csv-import-restored-banner')).not.toBeInTheDocument()
    await expect.element(view.getByRole('button', { name: /^Import 0 Records$/i })).toBeInTheDocument()
  })

  it('abandons a running import when the account changes mid-flight: A results never surface for B', async () => {
    let settle: (v: unknown) => void = () => {}
    apiPostMock.mockImplementation(() => new Promise((resolve) => { settle = resolve }))
    signIn('user-aaaa')

    const view = await renderWithClient(<Harness />)
    await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
    await userEvent.fill(view.getByPlaceholder(/employee_code/), CSV)
    await userEvent.click(view.getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })

    // Account switches WHILE the POST is in flight; the late success verdict
    // arrives after the owner changed. It must not render and must not be
    // stored for restore.
    apiPostMock.mockImplementation(() => Promise.resolve({ data: {} }))
    signIn('user-bbbb')
    settle({ data: {} })

    // The stale wizard wipes its own view (defense: abandoned instance).
    await expect.element(view.getByRole('button', { name: /^Import 0 Records$/i })).toBeInTheDocument()
    await expect.element(view.getByText(/1 succeeded/)).not.toBeInTheDocument()
    await userEvent.click(view.getByTestId('csv-import-close-button'))
    await vi.waitFor(() => {
      expect(view.getByPlaceholder(/employee_code/)).not.toBeInTheDocument()
    })

    // And a fresh mount for B still sees nothing from A's import.
    await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
    await expect.element(view.getByText(/1 succeeded/)).not.toBeInTheDocument()
    await expect.element(view.getByTestId('csv-import-restored-banner')).not.toBeInTheDocument()
    await expect.element(view.getByRole('button', { name: /^Import 0 Records$/i })).toBeInTheDocument()
  })

  it('still restores the unresolved batch with ORIGINAL keys for the SAME account (QA-01 preserved)', async () => {
    const capturedKeys: string[] = []
    apiPostMock.mockImplementation((_url: string, body: { source_ref?: string }) => {
      capturedKeys.push(body.source_ref ?? '')
      return Promise.reject({ response: { status: 502 } })
    })
    signIn('user-aaaa')

    const view = await renderWithClient(<Harness />)
    await importUnresolvedAndClose(view)

    await userEvent.click(view.getByRole('button', { name: 'Open wizard' }))
    await expect.element(view.getByTestId('csv-import-restored-banner')).toBeInTheDocument()
    await expect.element(view.getByText(/1 unknown/i)).toBeInTheDocument()

    // Reconcile on the restored batch asks the server about the ORIGINAL key.
    apiPostMock.mockReset()
    apiPostMock.mockResolvedValue({ data: { results: [{ employee_code: 'EMP001', source_ref: capturedKeys[0], status: 'not_found' }] } })
    await userEvent.click(view.getByRole('button', { name: /reconcile/i }))
    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledWith('/daily-time-records/reconcile-imports', {
        keys: [{ employee_code: 'EMP001', source_ref: capturedKeys[0] }],
      })
    })
  })
})
