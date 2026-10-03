import { useState } from 'react'
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { AttendanceCsvImportWizard, __resetRecoverableSlotForTests } from './components/csv-import/attendance-csv-wizard'

const { apiPostMock, toastSuccessMock, toastErrorMock, toastWarningMock, toastInfoMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastWarningMock: vi.fn(),
  toastInfoMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({
  api: { post: (...a: unknown[]) => apiPostMock(...a) },
}))
vi.mock('sonner', () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccessMock(...a),
    error: (...a: unknown[]) => toastErrorMock(...a),
    warning: (...a: unknown[]) => toastWarningMock(...a),
    info: (...a: unknown[]) => toastInfoMock(...a),
  },
}))

const CSV2 = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
  'EMP002,2026-08-04T09:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')
const CSV1 = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')

const RECONCILE_URL = '/daily-time-records/reconcile-imports'

// Branch the single mocked api.post between import writes and the bounded
// reconcile API by request URL.
function routeCalls(importImpl: (url: string, body?: unknown) => unknown, reconcileImpl?: (url: string, body?: unknown) => unknown) {
  apiPostMock.mockImplementation((url: string, ...rest: unknown[]) =>
    url === RECONCILE_URL && reconcileImpl ? reconcileImpl(url, ...rest) : importImpl(url, ...rest)
  )
}

function reconcileResponse(verdicts: Array<{ employee_code: string; source_ref: string; status: string; record_id?: string }>) {
  return {
    data: {
      results: verdicts.map(v => ({ ...v, record_id: v.record_id ?? null })),
      unresolved: verdicts.filter(v => v.status === 'unresolved').length,
      requested: verdicts.length,
    },
  }
}

describe('Attendance CSV import idempotency (QA-01)', () => {
  beforeEach(() => {
    apiPostMock.mockReset()
    toastSuccessMock.mockReset()
    toastErrorMock.mockReset()
    toastWarningMock.mockReset()
    toastInfoMock.mockReset()
    __resetRecoverableSlotForTests()
  })

  it('sends a stable opaque per-row source_ref key with every row', async () => {
    routeCalls(() => Promise.resolve({ data: {} }))

    const { getByRole, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV2)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))

    await vi.waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(2)
    })
    const k0 = (apiPostMock.mock.calls[0][1] as Record<string, string>).source_ref
    const k1 = (apiPostMock.mock.calls[1][1] as Record<string, string>).source_ref
    expect(k0).toMatch(/^dtr-import-[a-z0-9]+-r0$/)
    expect(k1).toMatch(/^dtr-import-[a-z0-9]+-r1$/)
    expect(k0).not.toBe(k1)
  })

  it('lost response -> UNKNOWN blocks retry; Reconcile (employee+key pairs) resolves committed row; retry keeps its key', async () => {
    let postCount = 0
    routeCalls(() => {
      postCount += 1
      if (postCount === 1) return Promise.reject(new Error('Network Error'))
      if (postCount === 2) return Promise.reject({ response: { status: 422, data: { detail: 'bad row' } } })
      return Promise.resolve({ data: { id: 'dtr-2' } })
    })

    const { getByRole, getByText, getByPlaceholder, getByTestId } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV2)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))
    await vi.waitFor(() => { expect(postCount).toBe(2) })

    const key1 = (apiPostMock.mock.calls[0][1] as Record<string, string>).source_ref
    const key2 = (apiPostMock.mock.calls[1][1] as Record<string, string>).source_ref

    await expect.element(getByText(/1 unknown/i)).toBeInTheDocument()
    await expect.element(getByText(/1 failed/i)).toBeInTheDocument()
    await expect.element(getByTestId('csv-row-status-2')).toHaveTextContent(/Unknown/)
    await expect.element(getByTestId('csv-row-status-3')).toHaveTextContent(/Failed/)
    await expect.element(getByRole('button', { name: /^Retry 2 Records$/i })).toBeDisabled()
    expect(toastErrorMock).toHaveBeenCalledWith(expect.stringContaining('awaiting reconciliation'))

    // Reconcile posts employee+identity PAIRS — bounded, scoped, exact.
    let reconcileBody: { keys: Array<{ employee_code: string; source_ref: string }> } | null = null
    routeCalls(() => Promise.resolve({ data: {} }), (_url, body) => {
      reconcileBody = body as { keys: Array<{ employee_code: string; source_ref: string }> }
      return Promise.resolve(reconcileResponse([
        { employee_code: 'EMP001', source_ref: key1, status: 'committed', record_id: 'dtr-1' },
      ]))
    })
    await userEvent.click(getByRole('button', { name: /reconcile/i }))
    await vi.waitFor(() => { expect(reconcileBody).not.toBeNull() })

    expect(reconcileBody!.keys).toEqual([
      { employee_code: 'EMP001', source_ref: key1 },
    ])
    await expect.element(getByText(/1 succeeded/i)).toBeInTheDocument()
    await expect.element(getByText(/1 unknown/i)).not.toBeInTheDocument()
    expect(toastSuccessMock).toHaveBeenCalledWith(expect.stringContaining('already recorded'))

    // Retry now targets ONLY the failed row and reuses its stable key.
    await userEvent.click(getByRole('button', { name: /^Retry 1 Records$/i }))
    // Calls: [0] row1 import, [1] row2 import, [2] reconcile, [3] retry.
    await vi.waitFor(() => { expect(apiPostMock.mock.calls.length).toBe(4) })
    const retryPayload = apiPostMock.mock.calls[3][1] as Record<string, string>
    expect(retryPayload.employee_code).toBe('EMP002')
    expect(retryPayload.source_ref).toBe(key2)
    await expect.element(getByText(/2 succeeded/i)).toBeInTheDocument()
  })

  it('reconcile not_found converts the row to a safe retry while preserving the key', async () => {
    routeCalls(() => Promise.reject(new Error('timeout')))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
    const key = (apiPostMock.mock.calls[0][1] as Record<string, string>).source_ref

    routeCalls(() => Promise.resolve({ data: { id: 'late' } }), () =>
      Promise.resolve(reconcileResponse([{ employee_code: 'EMP001', source_ref: key, status: 'not_found' }]))
    )
    await userEvent.click(getByRole('button', { name: /reconcile/i }))

    await expect.element(getByText(/retry is safe/i)).toBeInTheDocument()
    const retry = getByRole('button', { name: /^Retry 1 Records$/i })
    await expect.element(retry).toBeEnabled()

    await userEvent.click(retry)
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(3) })
    // The retry call (the third post overall: import, reconcile, retry) keeps
    // the SAME identity so a late commit is deduped server-side.
    const retryPayload = apiPostMock.mock.calls[2][1] as Record<string, string>
    expect(retryPayload.source_ref).toBe(key)
  })

  it('reconcile deleted retires the identity — no resurrection, no silent retry', async () => {
    routeCalls(() => Promise.reject(new Error('Network Error')))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
    const key = (apiPostMock.mock.calls[0][1] as Record<string, string>).source_ref

    routeCalls(() => Promise.resolve({ data: {} }), () =>
      Promise.resolve(reconcileResponse([{ employee_code: 'EMP001', source_ref: key, status: 'deleted' }]))
    )
    await userEvent.click(getByRole('button', { name: /reconcile/i }))

    await expect.element(getByText(/retired/i)).toBeInTheDocument()
    expect(toastErrorMock).toHaveBeenCalledWith(expect.stringContaining('deleted deliberately'))
  })

  it('reconcile unresolved keeps UNKNOWN and retry blocked (no visibility != no commit)', async () => {
    routeCalls(() => Promise.reject(new Error('Network Error')))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
    const key = (apiPostMock.mock.calls[0][1] as Record<string, string>).source_ref

    routeCalls(() => Promise.resolve({ data: {} }), () =>
      Promise.resolve(reconcileResponse([{ employee_code: 'EMP001', source_ref: key, status: 'unresolved' }]))
    )
    await userEvent.click(getByRole('button', { name: /reconcile/i }))

    await expect.element(getByText(/1 unknown/i)).toBeInTheDocument()
    await expect.element(getByText(/stays Unknown/i)).toBeInTheDocument()
    await expect.element(getByRole('button', { name: /^Retry 1 Records$/i })).toBeDisabled()
  })

  it('ambiguous 5xx is UNKNOWN, never treated as a definite non-commit', async () => {
    routeCalls(() => Promise.reject({ response: { status: 500, data: { detail: 'boom' } } }))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })

    await expect.element(getByText(/1 unknown/i)).toBeInTheDocument()
    await expect.element(getByText(/Server error 500 — outcome unknown/i)).toBeInTheDocument()
    await expect.element(getByRole('button', { name: /^Retry 1 Records$/i })).toBeDisabled()
  })

  it('definite 4xx rejection is an error, not unknown, and is retry-safe', async () => {
    routeCalls(() => Promise.reject({ response: { status: 409, data: { detail: 'Import row changed since the first attempt' } } }))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })

    await expect.element(getByText(/1 failed/i)).toBeInTheDocument()
    await expect.element(getByText(/Import row changed since the first attempt/i)).toBeInTheDocument()
    await expect.element(getByRole('button', { name: /reconcile/i })).not.toBeInTheDocument()
    await expect.element(getByRole('button', { name: /^Retry 1 Records$/i })).toBeEnabled()
  })

  it('closing with unresolved rows preserves identities; reopening restores the batch and blocks CSV edits', async () => {
    const postCalls: Array<{ url: string; body: Record<string, string> }> = []
    routeCalls((url, body) => {
      postCalls.push({ url, body: body as Record<string, string> })
      return Promise.reject(new Error('Network Error'))
    })

    // Mirrors the real page mount (`{importOpen && <Wizard/>}`): closing
    // UNMOUNTS the wizard, so only the module-level recoverable slot can
    // preserve identities across reopen.
    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>Open wizard</button>
          {open && <AttendanceCsvImportWizard open={open} onOpenChange={setOpen} />}
        </>
      )
    }

    const { getByRole, getByText, getByPlaceholder, getByTestId } = await renderWithClient(<Harness />)
    await userEvent.click(getByRole('button', { name: 'Open wizard' }))
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(postCalls.length).toBe(1) })
    const key = postCalls[0].body.source_ref
    await expect.element(getByText(/1 unknown/i)).toBeInTheDocument()

    // Close with UNKNOWN rows — identities must survive the unmount.
    await userEvent.click(getByTestId('csv-import-close-button'))
    await vi.waitFor(() => {
      expect(getByPlaceholder(/employee_code/)).not.toBeInTheDocument()
    })

    // Reopen: same batch restored (banner + unknown count), editor locked.
    await userEvent.click(getByRole('button', { name: 'Open wizard' }))
    await expect.element(getByTestId('csv-import-restored-banner')).toBeInTheDocument()
    await expect.element(getByText(/1 unknown/i)).toBeInTheDocument()
    await expect.element(getByPlaceholder(/employee_code/)).toBeDisabled()

    // Reconcile uses the ORIGINAL keys — proves identity preservation.
    routeCalls(() => Promise.resolve({ data: {} }), (_url, body) => {
      const req = body as { keys: Array<{ employee_code: string; source_ref: string }> }
      expect(req.keys).toEqual([{ employee_code: 'EMP001', source_ref: key }])
      return Promise.resolve(reconcileResponse([{ employee_code: 'EMP001', source_ref: key, status: 'not_found' }]))
    })
    await userEvent.click(getByRole('button', { name: /reconcile/i }))
    await expect.element(getByText(/retry is safe/i)).toBeInTheDocument()
  })

  it('Discard explicitly abandons unresolved identities', async () => {
    routeCalls(() => Promise.reject(new Error('Network Error')))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })

    await userEvent.click(getByRole('button', { name: /^Discard$/i }))
    expect(toastWarningMock).toHaveBeenCalledWith(expect.stringContaining('discarded'))
    await expect.element(getByText(/1 unknown/i)).not.toBeInTheDocument()
    await expect.element(getByRole('button', { name: /^Retry 1 Records$/i })).toBeEnabled()
    await expect.element(getByPlaceholder(/employee_code/)).toBeEnabled()
  })

  it('a 200 replay response counts as success', async () => {
    routeCalls(() => Promise.resolve({ status: 200, data: { id: 'existing' } }))

    const { getByRole, getByText, getByPlaceholder } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )

    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })
    await expect.element(getByText(/1 succeeded/i)).toBeInTheDocument()
    expect(toastSuccessMock).toHaveBeenCalledWith('Successfully imported 1 time records')
  })
})
