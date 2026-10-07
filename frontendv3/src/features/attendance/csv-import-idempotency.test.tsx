import { useState } from 'react'
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { AttendanceCsvImportWizard, __resetRecoverableSlotForTests } from './components/csv-import/attendance-csv-wizard'

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))

const { apiPostMock, toastSuccessMock, toastErrorMock, toastWarningMock, toastInfoMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastWarningMock: vi.fn(),
  toastInfoMock: vi.fn(),
}))
vi.mock('@/lib/api/client', () => ({
  api: { post: (...a: unknown[]) => apiPostMock(...a) },
  getAccessToken: () => undefined,
  getRefreshToken: () => undefined,
  clearTokens: () => {},
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
  'EMP002,2026-08-05T09:00:00Z,2026-08-05T17:00:00Z,DAY',
].join('\n')
const CSV1 = [
  'employee_code,login_date,logout_date,shift_code',
  'EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY',
].join('\n')
const PREFLIGHT_URL = '/daily-time-records/import-batches/preflight'
const COMMIT_URL = '/daily-time-records/import-batches/commit'
const RECONCILE_URL = '/daily-time-records/reconcile-imports'
type ImportReply = (body: unknown) => unknown

function routeCalls(preflight: ImportReply, commit: ImportReply, reconcile: ImportReply = () => Promise.resolve({ data: {} })) {
  apiPostMock.mockImplementation((url: string, body: unknown) => {
    if (url === PREFLIGHT_URL) return preflight(body)
    if (url === COMMIT_URL) return commit(body)
    if (url === RECONCILE_URL) return reconcile(body)
    throw new Error(`Unexpected POST ${url}`)
  })
}

function validPreflight() {
  return { data: { valid: true, issues: [], excluded: [] } }
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

  it('preflights one complete batch and sends stable row identities on commit', async () => {
    routeCalls(() => Promise.resolve(validPreflight()), () => Promise.resolve({ data: {} }))
    const { getByRole, getByPlaceholder, unmount } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV2)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))
    await vi.waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(2))

    const preflight = apiPostMock.mock.calls[0][1] as { batch_id: string; rows: unknown[] }
    const commit = apiPostMock.mock.calls[1][1] as typeof preflight
    expect(preflight.batch_id).toMatch(/^[0-9a-f-]{36}$/i)
    expect(commit).toEqual(preflight)
    expect(preflight.rows).toHaveLength(2)
    await unmount()
  })

  it('lost atomic commit response blocks retry; reconciliation settles the exact row keys', async () => {
    let capturedKeys: Array<{ employee_code: string; source_ref: string }> = []
    routeCalls(
      () => Promise.resolve(validPreflight()),
      () => Promise.reject(new Error('Network Error')),
      body => {
        capturedKeys = (body as { keys: Array<{ employee_code: string; source_ref: string }> }).keys
        return Promise.resolve(reconcileResponse(capturedKeys.map((pair, index) => ({
          ...pair,
          status: 'committed',
          record_id: `dtr-${index + 1}`,
        }))))
      },
    )
    const { getByRole, getByText, getByPlaceholder, getByTestId, unmount } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV2)
    await userEvent.click(getByRole('button', { name: /^Import 2 Records$/i }))
    await expect.element(getByTestId('csv-import-unknown-count')).toHaveTextContent('2 unknown')
    await expect.element(getByRole('button', { name: /^Retry 2 Records$/i })).toBeDisabled()

    await userEvent.click(getByRole('button', { name: /^Reconcile$/i }))
    await expect.element(getByText(/2 succeeded/i)).toBeInTheDocument()
    expect(capturedKeys).toHaveLength(2)
    expect(capturedKeys[0].source_ref).toMatch(/^dtr-import-[0-9a-f-]{36}-r0$/i)
    expect(capturedKeys[1].source_ref).toMatch(/^dtr-import-[0-9a-f-]{36}-r1$/i)
    await expect.element(getByRole('button', { name: /^Retry 0 Records$/i })).toBeDisabled()
    await unmount()
  })

  it('not_found permits retry with the same batch identity and row key', async () => {
    let attempts = 0
    const commitBodies: Array<{ batch_id: string; rows: unknown[] }> = []
    routeCalls(
      () => Promise.resolve(validPreflight()),
      body => {
        attempts += 1
        commitBodies.push(body as { batch_id: string; rows: unknown[] })
        return attempts === 1 ? Promise.reject(new Error('timeout')) : Promise.resolve({ data: {} })
      },
      body => {
        const pair = (body as { keys: Array<{ employee_code: string; source_ref: string }> }).keys[0]
        return Promise.resolve(reconcileResponse([{ ...pair, status: 'not_found' }]))
      },
    )
    const { getByRole, getByText, getByPlaceholder, getByTestId, unmount } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await userEvent.click(getByRole('button', { name: /^Reconcile$/i }))
    await expect.element(getByTestId('csv-correction-row-2').getByText(/retry is safe/i)).toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /^Retry 1 Records$/i }))
    await vi.waitFor(() => expect(attempts).toBe(2))
    expect(commitBodies[1]).toEqual(commitBodies[0])
    await expect.element(getByText(/1 succeeded/i)).toBeInTheDocument()
    await unmount()
  })

  it('deleted identities retire and unresolved identities remain blocked', async () => {
    for (const verdict of ['deleted', 'unresolved'] as const) {
      __resetRecoverableSlotForTests()
      apiPostMock.mockReset()
      routeCalls(
        () => Promise.resolve(validPreflight()),
        () => Promise.reject(new Error('Network Error')),
        body => {
          const pair = (body as { keys: Array<{ employee_code: string; source_ref: string }> }).keys[0]
          return Promise.resolve(reconcileResponse([{ ...pair, status: verdict }]))
        },
      )
      const { getByRole, getByPlaceholder, getByTestId, unmount } = await renderWithClient(
        <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
      )
      await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
      await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
      await userEvent.click(getByRole('button', { name: /^Reconcile$/i }))
      if (verdict === 'deleted') {
        await expect.element(getByTestId('csv-correction-row-2').getByText(/retired/i)).toBeInTheDocument()
        await expect.element(getByRole('button', { name: /^Retry 0 Records$/i })).toBeDisabled()
      } else {
        await expect.element(getByTestId('csv-row-status-2').getByText('Unknown')).toBeInTheDocument()
        await expect.element(getByRole('button', { name: /^Retry 1 Records$/i })).toBeDisabled()
      }
      await unmount()
    }
  })

  it('ambiguous commit 5xx is UNKNOWN; a definite commit 4xx is a retry-safe failure', async () => {
    routeCalls(
      () => Promise.resolve(validPreflight()),
      () => Promise.reject({ response: { status: 500, data: { detail: 'boom' } } }),
    )
    const first = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await userEvent.fill(first.getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(first.getByRole('button', { name: /^Import 1 Records$/i }))
    await expect.element(first.getByTestId('csv-import-unknown-count')).toHaveTextContent('1 unknown')
    await expect.element(first.getByRole('button', { name: /^Retry 1 Records$/i })).toBeDisabled()
    await first.unmount()

    __resetRecoverableSlotForTests()
    apiPostMock.mockReset()
    routeCalls(
      () => Promise.resolve(validPreflight()),
      () => Promise.reject({ response: { status: 409, data: { detail: 'Batch identity conflict' } } }),
    )
    const second = await renderWithClient(<AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />)
    await userEvent.fill(second.getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(second.getByRole('button', { name: /^Import 1 Records$/i }))
    await expect.element(second.getByText(/1 failed/i)).toBeInTheDocument()
    await expect.element(second.getByRole('button', { name: /^Retry 1 Records$/i })).toBeEnabled()
    await second.unmount()
  })

  it('closing with unresolved rows preserves original row identities across unmount and reopen', async () => {
    let retryKey = ''
    routeCalls(
      () => Promise.resolve(validPreflight()),
      () => Promise.reject(new Error('Network Error')),
      body => {
        const pair = (body as { keys: Array<{ employee_code: string; source_ref: string }> }).keys[0]
        retryKey = pair.source_ref
        return Promise.resolve(reconcileResponse([{ ...pair, status: 'not_found' }]))
      },
    )
    function Harness() {
      const [open, setOpen] = useState(false)
      return <><button type="button" onClick={() => setOpen(true)}>Open wizard</button>{open && <AttendanceCsvImportWizard open={open} onOpenChange={setOpen} />}</>
    }
    const { getByRole, getByPlaceholder, getByTestId, unmount } = await renderWithClient(<Harness />)
    await userEvent.click(getByRole('button', { name: 'Open wizard' }))
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await expect.element(getByTestId('csv-import-unknown-count')).toHaveTextContent('1 unknown')
    await userEvent.click(getByTestId('csv-import-close-button'))
    await vi.waitFor(() => expect(getByPlaceholder(/employee_code/)).not.toBeInTheDocument())
    await userEvent.click(getByRole('button', { name: 'Open wizard' }))
    await expect.element(getByTestId('csv-import-restored-banner')).toBeInTheDocument()
    await expect.element(getByPlaceholder(/employee_code/)).toBeDisabled()
    await userEvent.click(getByRole('button', { name: /^Reconcile$/i }))
    await expect.element(getByTestId('csv-correction-row-2').getByText(/retry is safe/i)).toBeInTheDocument()
    expect(retryKey).toMatch(/^dtr-import-[0-9a-f-]{36}-r0$/i)
    await unmount()
  })

  it('Discard explicitly releases unresolved import identities', async () => {
    routeCalls(() => Promise.resolve(validPreflight()), () => Promise.reject(new Error('Network Error')))
    const { getByRole, getByPlaceholder, getByTestId, unmount } = await renderWithClient(
      <AttendanceCsvImportWizard open={true} onOpenChange={() => {}} />
    )
    await userEvent.fill(getByPlaceholder(/employee_code/), CSV1)
    await userEvent.click(getByRole('button', { name: /^Import 1 Records$/i }))
    await userEvent.click(getByRole('button', { name: /^Discard$/i }))
    expect(toastWarningMock).toHaveBeenCalledWith(expect.stringContaining('discarded'))
    await expect.element(getByTestId('csv-import-unknown-count')).not.toBeInTheDocument()
    await expect.element(getByPlaceholder(/employee_code/)).toBeEnabled()
    await unmount()
  })
})
