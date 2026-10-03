// PR74 review P2 regressions: Reconcile must never send more than the
// server's 200-pair bound in one request (a 422 rejects the WHOLE batch and
// strands every unresolved row), and a chunk that fails in transit must
// neither strand nor wrongly unlock rows — settled verdicts still apply and
// the next attempt re-verifies exactly the remaining pairs.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { AttendanceCsvImportWizard, __resetRecoverableSlotForTests } from './components/csv-import/attendance-csv-wizard'

const { apiPostMock, toastErrorMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({
  api: { post: (...a: unknown[]) => apiPostMock(...a) },
  // auth-store hydrate() reads these at import time; no session in these tests.
  getAccessToken: () => undefined,
  getRefreshToken: () => undefined,
  clearTokens: () => {},
}))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: (...a: unknown[]) => toastErrorMock(...a), warning: vi.fn(), info: vi.fn() },
}))

const RECONCILE_URL = '/daily-time-records/reconcile-imports'

function csvRows(n: number): string {
  const lines = ['employee_code,login_date,logout_date,shift_code']
  for (let i = 0; i < n; i++) {
    lines.push(`EMP${String(i).padStart(4, '0')},2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY`)
  }
  return lines.join('\n')
}

/** Import `n` rows, every POST dying with an ambiguous 5xx -> all UNKNOWN. */
async function importAllUnknown(view: Awaited<ReturnType<typeof renderWithClient>>, n: number) {
  apiPostMock.mockRejectedValue({ response: { status: 502 } })
  await userEvent.fill(view.getByPlaceholder(/employee_code/), csvRows(n))
  await userEvent.click(view.getByRole('button', { name: new RegExp(`^Import ${n} Records$`, 'i') }))
  await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(n) })
  // Drop the import POSTs from the call log; reconcile asserts below only
  // look at the /reconcile-imports requests.
  apiPostMock.mockReset()
}

function reconcileChunk(callNo: number) {
  return (body: { keys: Array<{ employee_code: string; source_ref: string }> }) => ({
    data: {
      results: body.keys.map((k) => ({ ...k, status: 'not_found', record_id: null })),
      unresolved: 0,
      requested: body.keys.length,
    },
    __call: callNo,
  })
}

beforeEach(() => {
  __resetRecoverableSlotForTests()
  apiPostMock.mockReset()
  toastErrorMock.mockReset()
})

describe('Attendance CSV reconcile chunking (PR74 review P2)', () => {
  it('splits 401 unresolved rows into sequential 200/200/1 requests and settles all of them', async () => {
    const view = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await importAllUnknown(view, 401)

    await expect.element(view.getByTestId('csv-import-unknown-count')).toHaveTextContent('401 unknown')

    const reconcileCalls: number[] = []
    apiPostMock.mockImplementation((url: string, body: { keys: unknown[] }) => {
      expect(url).toBe(RECONCILE_URL)
      reconcileCalls.push(body.keys.length)
      return Promise.resolve(reconcileChunk(reconcileCalls.length)(body as never))
    })

    await userEvent.click(view.getByRole('button', { name: /^Reconcile$/i }))
    await vi.waitFor(() => {
      expect(reconcileCalls).toEqual([200, 200, 1])
    })

    // All 401 pairs were asked about; not_found verdicts unlocked every row
    // (unknown count gone, Retry enabled).
    await expect.element(view.getByTestId('csv-import-unknown-count')).not.toBeInTheDocument()
    await expect.element(view.getByRole('button', { name: /^Retry 401 Records$/i })).toBeEnabled()
  })

  it('asks exactly 200 pairs in one request when the bound is hit to the row', async () => {
    const view = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await importAllUnknown(view, 200)

    const sizes: number[] = []
    apiPostMock.mockImplementation((_url: string, body: { keys: unknown[] }) => {
      sizes.push(body.keys.length)
      return Promise.resolve(reconcileChunk(1)(body as never))
    })

    await userEvent.click(view.getByRole('button', { name: /^Reconcile$/i }))
    await vi.waitFor(() => { expect(sizes).toEqual([200]) })
    // Exactly at the cap: one request, no spurious second chunk.
    expect(apiPostMock).toHaveBeenCalledTimes(1)
  })

  it('a failed second chunk keeps first-chunk verdicts applied, leaves the rest UNKNOWN with retry blocked', async () => {
    const view = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await importAllUnknown(view, 250)

    let chunk = 0
    const askedBatches: Array<Array<{ employee_code: string; source_ref: string }>> = []
    apiPostMock.mockImplementation((_url: string, body: { keys: Array<{ employee_code: string; source_ref: string }> }) => {
      chunk += 1
      askedBatches.push(body.keys)
      if (chunk === 1) return Promise.resolve(reconcileChunk(1)(body))
      return Promise.reject(new Error('Network Error'))
    })

    await userEvent.click(view.getByRole('button', { name: /^Reconcile$/i }))
    await vi.waitFor(() => {
      // 200 settled + 50 stranded; the 250-pair tail was never asked again.
      expect(askedBatches.length).toBe(2)
      expect(askedBatches[0].length).toBe(200)
      expect(askedBatches[1].length).toBe(50)
    })
    expect(apiPostMock).toHaveBeenCalledTimes(2)

    // 50 rows still UNKNOWN -> editor locked; the Retry button covers every
    // non-success row (200 settled-as-error + 50 unknown) and stays blocked.
    await expect.element(view.getByTestId('csv-import-unknown-count')).toHaveTextContent('50 unknown')
    await expect.element(view.getByRole('button', { name: /^Retry 250 Records$/i })).toBeDisabled()

    // Second attempt: ONLY the remaining pairs are re-verified (fresh verdicts
    // — the settled 200 are not asked about again).
    chunk = 0
    apiPostMock.mockImplementation((_url: string, body: { keys: Array<{ employee_code: string; source_ref: string }> }) => {
      chunk += 1
      askedBatches.push(body.keys)
      return Promise.resolve(reconcileChunk(2 + chunk)(body))
    })
    await userEvent.click(view.getByRole('button', { name: /^Reconcile$/i }))
    await vi.waitFor(() => {
      expect(askedBatches.length).toBe(3)
      expect(askedBatches[2].length).toBe(50)
    })

    // Everything settled now: no UNKNOWN remains, retry enabled.
    await expect.element(view.getByTestId('csv-import-unknown-count')).not.toBeInTheDocument()
    await expect.element(view.getByRole('button', { name: /^Retry 250 Records$/i })).toBeEnabled()
  })

  it('a first-chunk failure is the plain all-stay-unknown path (message + blocked retry)', async () => {
    const view = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await importAllUnknown(view, 250)

    apiPostMock.mockRejectedValue(new Error('Network Error'))
    await userEvent.click(view.getByRole('button', { name: /^Reconcile$/i }))
    await vi.waitFor(() => { expect(apiPostMock).toHaveBeenCalledTimes(1) })

    expect(toastErrorMock).toHaveBeenCalledWith(expect.stringContaining('rows stay Unknown'))
    await expect.element(view.getByTestId('csv-import-unknown-count')).toHaveTextContent('250 unknown')
    await expect.element(view.getByRole('button', { name: /^Retry 250 Records$/i })).toBeDisabled()
  })
})
