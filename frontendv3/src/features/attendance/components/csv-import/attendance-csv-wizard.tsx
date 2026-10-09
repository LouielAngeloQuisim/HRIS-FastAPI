import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
// @ts-expect-error - papaparse has no type declarations
import Papa from 'papaparse'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api/client'
import { useAuthStore } from '@/stores/auth-store'
import { useCan } from '@/context/permissions-provider'
import { toast } from 'sonner'
import { AlertTriangle, CheckCircle2, Upload, XCircle } from 'lucide-react'

type CsvRow = Record<string, string>
// 'error'   = definite server verdict that the row was NOT committed (4xx) —
//             safe to correct + retry.
// 'unknown' = outcome unknown: no server verdict at all (transport failure),
//             OR an ambiguous 5xx that may have been raised after commit.
//             Blind retry stays blocked until deliberate Reconcile.
type ImportStatus = 'pending' | 'success' | 'error' | 'unknown'

interface RowResult {
  row: number
  data: CsvRow
  // Stable opaque identity for this import row, kept across retry,
  // reconciliation AND close/reopen: `dtr-import-<batch>-r<index>`. Never a
  // natural key, never re-derived from content.
  key: string
  status: ImportStatus
  error?: string
  code?: string
  workDate?: string
  retryable?: boolean
}

interface RecoverableBatch {
  batchId: string
  batchUuid: string
  csvText: string
  headers: string[]
  rows: CsvRow[]
  sourceRows: CsvRow[]
  results: RowResult[]
}

// The server bounds one reconcile request at 200 (employee, key) pairs
// (backend RECONCILE_MAX_KEYS, schemas.py) and rejects a larger WHOLE payload
// with 422 — which would leave every unresolved row stuck. The wizard
// therefore chunks proactively below that bound (PR74 review P2); the
// server-side limit remains the authoritative contract.
const RECONCILE_CHUNK_SIZE = 200

// Owner-bound single-slot in-memory store (never persisted to disk, never
// holds more than the CSV the user already has in the textarea). QA-01
// blocker: closing the dialog while rows are UNKNOWN must NOT discard their
// identities — a reopen restores the exact batch so Reconcile matches
// committed rows by their real keys and a retry reuses them (server-side
// dedupe makes any re-attempt duplicate-safe).
//
// PR74 review P1: that batch (employee CSV + identity keys + verdicts) is
// sensitive HR data of the account that created it, so it is bound to an
// OWNER key derived from the authenticated store:
//   - signed-in user id when hydrated (stable across token rotation; the
//     401 interceptor refreshes cookies, never the store identity), else
//   - the access token captured at sign-in (a fresh login always mints a
//     new one), else
//   - '' = identity unknown (page reloaded without re-login): a slot may
//     only match a slot with the same unknown identity, which within one
//     browser page session can only ever be the same person — any account
//     switch necessarily hydrates a different owner.
// Enforcement is two-layered:
//   1. A store subscription drops the slot the moment the owner key changes
//      (logout/reset, re-login, account switch) — invalidated, not transferred.
//   2. Restore requires an EXACT owner match at mount; a foreign slot is
//      cleared on the spot and no batch is handed over.
// Same user, same session: close/reopen keeps the same owner key, so the
// QA-01 recovery is fully preserved.
let recoverableSlot: { owner: string; batch: RecoverableBatch } | null = null

/** Current authenticated-session owner key; '' = identity unknown. */
function currentOwner(): string {
  const { user, accessToken } = useAuthStore.getState().auth
  if (user?.id) return `u:${user.id}`
  if (accessToken) return `t:${accessToken}`
  return ''
}

let lastOwner = currentOwner()
useAuthStore.subscribe(() => {
  const owner = currentOwner()
  if (owner !== lastOwner) {
    lastOwner = owner
    // Identity changed (logout, account switch, re-login): the previous
    // session's unresolved batch is invalidated — never transferred.
    recoverableSlot = null
  }
})

/** Test-only: reset the cross-close store between renders. */
export function __resetRecoverableSlotForTests() {
  recoverableSlot = null
}

const DTR_REQUIRED_FIELDS = ['employee_code', 'login_date', 'logout_date']

function hasUnresolved(results: RowResult[]): boolean {
  return results.some((r) => r.status === 'unknown')
}

type ReconcileVerdict = 'committed' | 'deleted' | 'not_found' | 'unresolved'

export function AttendanceCsvImportWizard({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  // Owner captured at mount (state, not a ref — this stays stable for the
  // lifetime of the mounted wizard). The slot is restored ONLY when its
  // owner matches exactly; a foreign slot is never handed over. All async
  // handlers re-check the live owner before touching shared state or the
  // slot (PR74 review P1).
  const [owner] = useState(currentOwner)
  const restored = useState(() =>
    recoverableSlot && recoverableSlot.owner === owner ? recoverableSlot.batch : null
  )[0]
  const [file, setFile] = useState<File | null>(null)
  const [csvText, setCsvText] = useState(() => restored?.csvText ?? '')
  const [parsedRows, setParsedRows] = useState<CsvRow[]>(() => restored?.rows ?? [])
  const [sourceRows, setSourceRows] = useState<CsvRow[]>(() => restored?.sourceRows ?? restored?.rows ?? [])
  const [headers, setHeaders] = useState<string[]>(() => restored?.headers ?? [])
  const [batchId, setBatchId] = useState(() => restored?.batchId ?? '')
  const [batchUuid, setBatchUuid] = useState(() => restored?.batchUuid ?? '')
  const [results, setResults] = useState<RowResult[]>(() => restored?.results ?? [])
  const [isImporting, setIsImporting] = useState(false)
  const [isReconciling, setIsReconciling] = useState(false)
  const [progress, setProgress] = useState(0)
  const [abandoned, setAbandoned] = useState(false)
  const [issueFilter, setIssueFilter] = useState('all')
  const [shiftOptions, setShiftOptions] = useState<Array<{ id: string; code: string; name: string }>>([])
  const [assignShiftByRow, setAssignShiftByRow] = useState<Record<number, string>>({})
  const [loadingShifts, setLoadingShifts] = useState(false)
  const canAssignShift = useCan('shifts', 'add')

  // Defense in depth: a slot owned by a DIFFERENT session is dropped on the
  // spot — it can never be restored, reconciled or retried by this account.
  useEffect(() => {
    if (recoverableSlot && recoverableSlot.owner !== owner) recoverableSlot = null
  }, [owner])

  const requiredFields = useMemo(() => DTR_REQUIRED_FIELDS, [])

  const keyForRow = useCallback(
    (index: number) => `dtr-import-${batchUuid}-r${index}`,
    [batchUuid],
  )

  const parseCsv = useCallback((text: string) => {
    const parsed = Papa.parse<CsvRow>(text, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false,
    })

    if (parsed.errors.length > 0) {
      toast.error(`CSV parse error: ${parsed.errors[0].message}`)
      return
    }

    const rows = parsed.data as CsvRow[]
    const cols = parsed.meta.fields ?? []

    setParsedRows(rows)
    setSourceRows(rows.map(row => ({ ...row })))
    setHeaders(cols)
    setBatchId(Math.random().toString(36).slice(2, 10))
    setBatchUuid(crypto.randomUUID())
    setResults([])
    setProgress(0)
  }, [])

  // Editing the CSV while unresolved identities exist would silently drop
  // them (and their committed rows). Blocked until Reconcile or Discard.
  const editingBlocked = hasUnresolved(results)

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (editingBlocked) {
      toast.error('Reconcile or discard unresolved rows before replacing the CSV — editing now would abandon import identities that may already be committed.')
      e.target.value = ''
      return
    }
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return

    if (selectedFile.type && !selectedFile.type.includes('csv') && !selectedFile.name.endsWith('.csv')) {
      toast.error('Please select a CSV file')
      return
    }

    setFile(selectedFile)
    const reader = new FileReader()
    reader.onload = (evt) => {
      const text = evt.target?.result as string
      setCsvText(text)
      parseCsv(text)
    }
    reader.readAsText(selectedFile)
  }, [parseCsv, editingBlocked])

  const handleTextareaChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (editingBlocked) {
      toast.error('Reconcile or discard unresolved rows before editing the CSV — changes now would abandon import identities that may already be committed.')
      return
    }
    setCsvText(e.target.value)
    setFile(null)
    if (e.target.value.trim()) {
      parseCsv(e.target.value)
    } else {
      setParsedRows([])
      setSourceRows([])
      setHeaders([])
      setBatchId('')
      setBatchUuid('')
      setResults([])
    }
  }, [parseCsv, editingBlocked])

  const mapColumns = (row: CsvRow, index: number) => ({
    employee_code: row.employee_code,
    login_date: row.login_date,
    logout_date: row.logout_date,
    shift_code: row.shift_code || undefined,
    source_row: sourceRows[index] ?? {},
    intervals: row.intervals_json ? (JSON.parse(row.intervals_json) as Array<{ start_at: string; end_at: string; source_row: CsvRow }>).map(({ start_at, end_at, source_row }) => ({ start_at, end_at, original_row: source_row })) : [],
  })

  const mergeDuplicateDateRows = useCallback((targetIndex: number) => {
    const targetResult = results[targetIndex]
    const target = parsedRows[targetIndex]
    if (!targetResult || !target || targetResult.code !== 'duplicate_employee_work_date' || !targetResult.workDate) return
    const matches = results.map((result, index) => ({ result, index, row: parsedRows[index] }))
      .filter(item => item.result.code === 'duplicate_employee_work_date'
        && item.result.workDate === targetResult.workDate
        && item.row?.employee_code?.trim().toUpperCase() === target.employee_code?.trim().toUpperCase())
    if (matches.length < 2) return
    const intervals = matches.flatMap(({ index, row }) => {
      if (!row) return []
      const saved = row.intervals_json ? JSON.parse(row.intervals_json) as Array<{ start_at: string; end_at: string; source_row: CsvRow }> : null
      return saved ?? [{ start_at: row.login_date, end_at: row.logout_date, source_row: sourceRows[index] ?? row }]
    }).sort((left, right) => Date.parse(left.start_at) - Date.parse(right.start_at))
    const merged = {
      ...target,
      login_date: intervals[0].start_at,
      logout_date: intervals[intervals.length - 1].end_at,
      intervals_json: JSON.stringify(intervals),
      merged_rows: String(intervals.length),
    }
    const removed = new Set(matches.slice(1).map(item => item.index))
    const nextRows = parsedRows.flatMap((row, index) => index === matches[0].index ? [merged] : removed.has(index) ? [] : [row])
    const nextSources = sourceRows.flatMap((row, index) => index === matches[0].index ? [row] : removed.has(index) ? [] : [row])
    setParsedRows(nextRows)
    setSourceRows(nextSources)
    setResults([])
    setAssignShiftByRow({})
    toast.success(`Merged ${matches.length} same-day rows into one daily record with ${intervals.length} intervals. Review it, then import.`)
  }, [parsedRows, results, sourceRows])

  const loadShiftOptions = useCallback(async () => {
    if (shiftOptions.length || loadingShifts) return
    setLoadingShifts(true)
    try {
      const { data } = await api.get<{ data: Array<{ id: string; code: string; name: string }> }>('/shifts', { params: { skip: 0, limit: 500 } })
      setShiftOptions(data.data.filter(item => item.id && item.code && item.name))
    } catch {
      toast.error('Could not load shifts. Check your shifts view permission and retry.')
    } finally {
      setLoadingShifts(false)
    }
  }, [shiftOptions.length, loadingShifts])

  const assignShiftForRow = useCallback(async (index: number) => {
    const row = parsedRows[index]
    const result = results[index]
    const employeeCode = row?.employee_code?.trim()
    const shift = shiftOptions.find(item => item.id === assignShiftByRow[index])
    const effectiveFrom = result?.workDate ?? row?.login_date?.slice(0, 10)
    if (!row || !employeeCode || !shift || !effectiveFrom) return
    const confirmed = window.confirm(`Assign ${shift.name} (${shift.code}) to ${employeeCode} starting ${effectiveFrom}? This is a separate audited change and remains even if you discard this attendance import.`)
    if (!confirmed) return
    try {
      await api.post('/employee-shift-assignments', { employee_code: employeeCode, shift_id: shift.id, effective_from: effectiveFrom, effective_to: null })
      setParsedRows(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, shift_code: shift.code } : item))
      toast.success(`Shift assignment saved for ${employeeCode} from ${effectiveFrom}. It is audited and is independent of this import.`)
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : error instanceof Error ? error.message : 'Could not assign the shift. Check permissions and effective-date conflicts.')
    }
  }, [parsedRows, results, shiftOptions, assignShiftByRow])

  const correctCell = useCallback((index: number, field: string, value: string) => {
    setParsedRows(current => current.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value } : row))
  }, [])

  const validateRow = useCallback((row: CsvRow): string | null => {
    const missing = requiredFields.filter(f => !row[f] || row[f].trim() === '')
    if (missing.length > 0) {
      return `Missing required fields: ${missing.join(', ')}`
    }
    return null
  }, [requiredFields])

  // Rows a (re)attempt targets: first run = every row; after a run = only the
  // rows that did not reach 'success'. Keys stay stable so the server can
  // dedupe a retry whose predecessor actually committed.
  const pendingIndices = useMemo(
    () =>
      parsedRows
        .map((_, i) => i)
        .filter((i) => results.length === 0 || (results[i]?.status !== 'success' && results[i]?.retryable !== false)),
    [parsedRows, results],
  )

  const unknownCount = results.filter(r => r.status === 'unknown').length

  // Live identity check for every async path (PR74 review P1): once the
  // signed-in account no longer matches this wizard's owner, the instance is
  // abandoned — no result commits, no slot writes, no UI state to leak.
  const identityLive = useCallback(() => !abandoned && currentOwner() === owner, [abandoned, owner])

  const abandonInstance = useCallback(() => {
    // Identity changed mid-operation: wipe the sensitive batch from THIS
    // wizard. The module slot is already dropped by the store subscription.
    setAbandoned(true)
    setFile(null)
    setCsvText('')
    setParsedRows([])
    setSourceRows([])
    setHeaders([])
    setBatchId('')
    setBatchUuid('')
    setResults([])
    setProgress(0)
    setIsImporting(false)
    setIsReconciling(false)
    toast.error('Signed-in account changed — this import was abandoned. Unresolved rows were not restored.')
  }, [])

  const handleImport = useCallback(async () => {
    if (parsedRows.length === 0) {
      toast.error('No data to import')
      return
    }
    if (unknownCount > 0) return
    if (results.some(row => row.retryable === false)) return
    if (!identityLive()) { abandonInstance(); return }

    setIsImporting(true)
    const current: RowResult[] = parsedRows.map((row, i) => ({
      row: i + 2,
      data: row,
      key: results[i]?.key ?? keyForRow(i),
      status: 'pending',
    }))
    const localIssues = parsedRows.flatMap((row, index) => {
      const message = validateRow(row)
      return message ? [{ row_index: index, message }] : []
    })
    if (localIssues.length > 0) {
      const issuesByRow = new Map(localIssues.map(issue => [issue.row_index, issue.message]))
      setResults(current.map((item, index) => {
        const issue = issuesByRow.get(index)
        return {
          ...item,
          status: 'error',
          error: issue ?? 'This row was not saved because another row in the batch needs correction.',
        }
      }))
      setIsImporting(false)
      toast.error(`Resolve ${localIssues.length} invalid row(s) before importing.`)
      return
    }

    const request = {
      batch_id: batchUuid,
      rows: parsedRows.map((row, index) => mapColumns(row, index)),
    }
    let preflight: {
      valid: boolean
      issues: Array<{ row_index: number; code: string; work_date?: string | null; employee_code: string; message: string }>
      excluded: Array<{ row_index: number; reason: string }>
    }
    try {
      const { data } = await api.post('/daily-time-records/import-batches/preflight', request)
      preflight = data
    } catch (err) {
      if (!identityLive()) { abandonInstance(); return }
      const detail = (err as { response?: { data?: { detail?: string | { message?: string } } } })?.response?.data?.detail
      const message = typeof detail === 'string' ? detail : detail?.message ?? 'Could not validate this attendance batch.'
      setResults(current.map(item => ({ ...item, status: 'error', error: message })))
      setIsImporting(false)
      toast.error(message)
      return
    }

    if (!identityLive()) { abandonInstance(); return }
    if (!preflight.valid) {
      const issuesByRow = new Map(preflight.issues.map(issue => [issue.row_index, issue]))
      setResults(current.map((item, index) => {
        const issue = issuesByRow.get(index)
        return {
          ...item,
          status: 'error',
          error: issue?.message ?? 'This row was not saved because another row in the batch needs correction.',
          code: issue?.code,
          workDate: issue?.work_date ?? undefined,
        }
      }))
      setIsImporting(false)
      toast.error(`Attendance needs correction in ${issuesByRow.size} row(s). Nothing was saved.`)
      return
    }

    const excludedByRow = new Map(preflight.excluded.map(item => [item.row_index, item.reason]))
    try {
      await api.post('/daily-time-records/import-batches/commit', request)
      if (!identityLive()) { abandonInstance(); return }
      const next = current.map((item, index) => ({
        ...item,
        status: 'success' as const,
        error: excludedByRow.get(index),
      }))
      await queryClient.invalidateQueries({ queryKey: ['daily-time-records'] })
      setResults(next)
      setProgress(100)
      const excludedCount = preflight.excluded.length
      toast.success(`Attendance batch saved. ${parsedRows.length - excludedCount} new, ${excludedCount} identical row(s) excluded.`)
    } catch (err) {
      if (!identityLive()) { abandonInstance(); return }
      const response = (err as {
        response?: {
          status?: number
          data?: {
            detail?: string | { message?: string; issues?: Array<{ row_index: number; message: string }> }
            error?: { message?: string }
          }
        }
      })?.response
      const status = response?.status
      const detail = response?.data?.detail
      if (status !== undefined && status >= 400 && status < 500) {
        const issues = typeof detail === 'object' ? detail?.issues ?? [] : []
        const issuesByRow = new Map(issues.map(issue => [issue.row_index, issue.message]))
        const message = response?.data?.error?.message
          ?? (typeof detail === 'string' ? detail : detail?.message)
          ?? `Server responded ${status}; no attendance was saved.`
        setResults(current.map((item, index) => ({
          ...item,
          status: 'error',
          error: issuesByRow.get(index) ?? message,
        })))
        toast.error('The server rejected the whole batch. Correct the listed rows and retry; no attendance was saved.')
      } else {
        const message = status
          ? `Server error ${status} — batch outcome unknown. Reconcile before retrying.`
          : 'No response received — batch outcome unknown. Reconcile before retrying.'
        setResults(current.map(item => ({ ...item, status: 'unknown', error: message })))
        toast.error('The import outcome is unknown. Reconcile before retrying; blind retry is blocked.')
      }
    } finally {
      setIsImporting(false)
    }
  }, [parsedRows, sourceRows, results, unknownCount, validateRow, queryClient, keyForRow, batchUuid, identityLive, abandonInstance])

  // Deliberate resolution of 'unknown' rows (QA-01): ask the server for a
  // verdict on each (employee, identity-key) PAIR via the bounded authorized
  // reconcile endpoint — never scan pages of unrelated rows, never match a
  // natural key, never treat "not in my visible scope" as "not committed".
  //
  // PR74 review P2: the endpoint accepts at most RECONCILE_MAX_KEYS (200)
  // pairs per request; oversized payloads are rejected whole (422), which
  // would strand every row. Requests are therefore split into sequential
  // chunks of <= 200. A transport failure on a chunk keeps every verdict
  // already collected (those rows settle), leaves the failed chunk's rows —
  // and any later chunks — UNKNOWN with retry blocked, and the next
  // Reconcile attempt re-verifies exactly those remaining pairs (server-side
  // verdicts are idempotent reads).
  const handleReconcile = useCallback(async () => {
    const unknowns = results.filter(r => r.status === 'unknown')
    if (unknowns.length === 0 || isReconciling) return
    if (!identityLive()) { abandonInstance(); return }

    setIsReconciling(true)
    const verdicts = new Map<string, { status: ReconcileVerdict; record_id?: string }>()
    const pairs = unknowns.map((r) => ({
      employee_code: r.data.employee_code,
      source_ref: r.key,
    }))
    let chunkFailed = false
    for (let start = 0; start < pairs.length; start += RECONCILE_CHUNK_SIZE) {
      if (!identityLive()) { abandonInstance(); return }
      const chunk = pairs.slice(start, start + RECONCILE_CHUNK_SIZE)
      try {
        const { data } = await api.post('/daily-time-records/reconcile-imports', { keys: chunk })
        for (const result of data.results) {
          verdicts.set(`${result.employee_code}\u0000${result.source_ref}`, {
            status: result.status,
            record_id: result.record_id,
          })
        }
      } catch {
        // Partial failure: stop issuing chunks, but KEEP and apply every
        // verdict already collected — settled rows unlock, the rest stay
        // UNKNOWN with retry blocked, and the next attempt re-verifies only
        // those remaining pairs. Nothing is stranded by a failed chunk.
        chunkFailed = true
        break
      }
    }
    if (!identityLive()) { abandonInstance(); return }

    if (chunkFailed && verdicts.size === 0) {
      // First chunk died with nothing settled: identical to the previous
      // whole-batch failure behavior — all rows stay UNKNOWN, retry blocked.
      toast.error('Could not reach the reconciliation service — rows stay Unknown. Try Reconcile again.')
      setIsReconciling(false)
      return
    }

    let matched = 0
    let retired = 0
    let freed = 0
    let kept = 0
    const next = results.map((r) => {
      if (r.status !== 'unknown') return r
      const v = verdicts.get(`${r.data.employee_code}\u0000${r.key}`)
      switch (v?.status) {
        case 'committed':
          matched += 1
          return { ...r, status: 'success' as ImportStatus, error: undefined }
        case 'deleted':
          // Deliberately deleted after commit: the identity is retired — no
          // automatic replay, a fresh explicit import must use a new batch.
          retired += 1
          return {
            ...r,
            status: 'error' as ImportStatus,
            retryable: false,
            error: 'Record was committed and then deleted deliberately — this import row is retired. Re-import deliberately if intended.',
          }
        case 'not_found':
          // Absent within the caller's visible scope at reconcile time. A
          // late commit is still possible, but the retry reuses this SAME
          // key and the race-safe create path dedupes it — so retry is safe.
          freed += 1
          return {
            ...r,
            status: 'error' as ImportStatus,
            error: 'No committed record found within visible scope - retry is safe (the same key dedupes a late commit).',
          }
        default:
          // 'unresolved' (out of visibility) or a missing verdict row: NOT
          // proof of anything. Stay unknown, retry stays blocked.
          kept += 1
          return {
            ...r,
            error: 'No definite verdict (outside visible scope) - stays Unknown; retry remains blocked.',
          }
      }
    })

    await queryClient.invalidateQueries({ queryKey: ['daily-time-records'] })
    setResults(next)
    setIsReconciling(false)

    if (matched > 0) toast.success(`Reconciled: ${matched} row(s) already recorded by this import`)
    if (retired > 0) toast.error(`${retired} row(s) were deleted deliberately - not resurrected`)
    if (kept > 0) toast.error(`${kept} row(s) could not be verified - retry stays blocked`)
    if (freed > 0 && kept === 0) toast.info('Reconciled: rows can now be retried safely.')
  }, [results, isReconciling, queryClient, identityLive, abandonInstance])

  // Explicit, warned abandonment of unresolved identities (their committed
  // rows, if any, stay in the database; only this client forgets the keys).
  const handleDiscard = useCallback(() => {
    setResults((prev) => prev.map((r) => (r.status === 'unknown'
      ? { ...r, status: 'error' as ImportStatus, error: 'Discarded unresolved identity - any late commit remains recorded and must be handled as a duplicate.' }
      : r)))
    toast.warning('Unresolved import identities discarded. Any row that actually committed is still in the system.')
  }, [])

  const handleClose = useCallback(() => {
    if (isImporting) return
    // Preserve unresolved batches across close/reopen (QA-01 blocker 3):
    // identities survive in-memory so a reopen reconciles/retries with the
    // SAME keys instead of starting a duplicate-safe-blind fresh batch.
    // The slot stays BOUND TO THIS OWNER — a stale (identity-changed)
    // instance never writes or clears the shared slot at all (PR74 P1).
    const live = identityLive()
    if (live && hasUnresolved(results) && parsedRows.length > 0) {
      recoverableSlot = {
        owner,
        batch: { batchId, batchUuid, csvText, headers, rows: parsedRows, sourceRows, results },
      }
    } else if (live) {
      recoverableSlot = null
      setTimeout(() => {
        setFile(null)
        setCsvText('')
        setParsedRows([])
        setSourceRows([])
        setHeaders([])
        setBatchId('')
        setBatchUuid('')
        setResults([])
        setProgress(0)
      }, 200)
    }
    onOpenChange(false)
  }, [isImporting, results, parsedRows, sourceRows, batchId, batchUuid, csvText, headers, onOpenChange, identityLive, owner])

  const successCount = results.filter(r => r.status === 'success').length
  const errorCount = results.filter(r => r.status === 'error').length
  const correctionResults = results
    .map((result, index) => ({ result, index }))
    .filter(({ result }) => result.status === 'error')
    .filter(({ result }) => {
      if (issueFilter === 'all') return true
      if (issueFilter === 'other') return !['missing_employee', 'missing_shift', 'incomplete_punch', 'duplicate_employee_work_date', 'saved_attendance_conflict'].includes(result.code ?? '')
      return result.code === issueFilter
    })

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import Attendance from CSV</DialogTitle>
          <DialogDescription>
            Upload a CSV file or paste CSV data to import time records in bulk. Required fields: {requiredFields.join(', ')}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {restored && unknownCount > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200" data-testid="csv-import-restored-banner">
              A previous import batch was restored with unresolved rows. Reconcile or discard them before editing the CSV or importing again — their keys are preserved so retries can never duplicate committed rows.
            </div>
          )}
          <div className="space-y-2">
            <Label>Upload CSV File</Label>
            <div className="flex items-center gap-2">
              <Input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                disabled={isImporting || editingBlocked}
                className="cursor-pointer"
              />
              {file && (
                <Button variant="ghost" size="icon" onClick={() => { setFile(null); setCsvText(''); setParsedRows([]); setSourceRows([]); setHeaders([]); }}>
                  <XCircle className="h-4 w-4" />
                </Button>
              )}
            </div>
            {file && <p className="text-sm text-muted-foreground">Selected: {file.name}</p>}
          </div>

          <div className="space-y-2">
            <Label>Or paste CSV data</Label>
            <Textarea
              value={csvText}
              onChange={handleTextareaChange}
              placeholder="employee_code,login_date,logout_date,shift_code&#10;EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY"
              rows={6}
              disabled={isImporting || editingBlocked}
            />
          </div>

          {parsedRows.length > 0 && (
            <div className="space-y-2">
              <Label>Preview ({parsedRows.length} rows)</Label>
              <div className="max-h-48 overflow-y-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      {headers.map(h => (
                        <th key={h} className="p-2 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {parsedRows.slice(0, 10).map((row, i) => (
                      <tr key={i} className="border-t">
                        {headers.map(h => (
                          <td key={h} className="p-2">{row[h] ?? '—'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {parsedRows.length > 10 && (
                  <p className="p-2 text-xs text-muted-foreground">Showing first 10 of {parsedRows.length} rows</p>
                )}
              </div>
            </div>
          )}

          {isImporting && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Importing...</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} />
            </div>
          )}

          {results.length > 0 && !isImporting && (
            <div className="space-y-2">
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1 text-green-600">
                  <CheckCircle2 className="h-4 w-4" /> {successCount} succeeded
                </span>
                {errorCount > 0 && (
                  <span className="flex items-center gap-1 text-destructive">
                    <XCircle className="h-4 w-4" /> {errorCount} failed
                  </span>
                )}
                {unknownCount > 0 && (
                  <span className="flex items-center gap-1 text-amber-600" data-testid="csv-import-unknown-count">
                    <AlertTriangle className="h-4 w-4" /> {unknownCount} unknown
                  </span>
                )}
              </div>
              {unknownCount > 0 && (
                <p className="text-xs text-muted-foreground">
                  Reconcile asks the server for a verdict on each unresolved (employee, import-key) pair —
                  committed rows are recognized by their exact identity keys, unverifiable rows stay Unknown
                  and retry stays blocked. Unresolved identities are also preserved if you close this dialog.
                </p>
              )}
              {errorCount > 0 && !editingBlocked && (
                <section className="space-y-3 rounded-md border border-amber-300 p-3" aria-label="Attendance corrections">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div><h3 className="font-medium">Review and correct failed rows</h3><p className="text-xs text-muted-foreground">No rows were saved. Corrections apply to this batch; the original CSV row is retained with the import record when saved.</p></div>
                    <label className="flex items-center gap-2 text-sm">Filter issues<select aria-label="Filter import issues" value={issueFilter} onChange={event => setIssueFilter(event.target.value)} className="h-9 rounded border bg-background px-2"><option value="all">All issues</option><option value="missing_employee">Missing employees</option><option value="missing_shift">Missing shifts</option><option value="incomplete_punch">Incomplete or invalid punches</option><option value="duplicate_employee_work_date">Duplicate employee/date</option><option value="saved_attendance_conflict">Saved attendance conflict</option><option value="other">Other</option></select></label>
                  </div>
                  <div className="max-h-72 space-y-3 overflow-y-auto">
                    {correctionResults.map(({ result, index }) => {
                      const corrected = parsedRows[index] ?? result.data
                      const source = sourceRows[index] ?? result.data
                      const intervals = corrected.intervals_json ? JSON.parse(corrected.intervals_json) as Array<{ start_at: string; end_at: string }> : [{ start_at: corrected.login_date, end_at: corrected.logout_date }]
                      const totalMinutes = intervals.reduce((total, interval) => {
                        const start = Date.parse(interval.start_at)
                        const end = Date.parse(interval.end_at)
                        return Number.isFinite(start) && Number.isFinite(end) && end > start ? total + Math.floor((end - start) / 60_000) : total
                      }, 0)
                      const hours = totalMinutes ? `${(totalMinutes / 60).toFixed(2)} hours across ${intervals.length} interval(s)` : 'not calculable'
                      return <article key={result.key} className="space-y-2 rounded border p-3" data-testid={`csv-correction-row-${result.row}`}>
                        <div className="flex flex-wrap justify-between gap-2 text-sm"><strong>CSV row {result.row} · {result.workDate ?? corrected.login_date?.slice(0, 10) ?? 'date missing'}</strong><span className="text-destructive">{result.error}</span></div>
                        <p className="text-xs text-muted-foreground">Original: {source.employee_code || 'no employee'} · {source.login_date || 'no login'} → {source.logout_date || 'no logout'} · {source.shift_code || 'no shift'}; calculated duration: {hours}</p>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {(['employee_code', 'login_date', 'logout_date', 'shift_code'] as const).map(field => <label key={field} className="grid gap-1 text-xs">{field.replace('_', ' ')}<input aria-label={`Correct row ${result.row} ${field}`} value={corrected[field] ?? ''} onChange={event => correctCell(index, field, event.target.value)} className="h-9 rounded border bg-background px-2" /></label>)}
                        </div>
                        {result.code === 'duplicate_employee_work_date' && result.workDate && <Button type="button" variant="outline" size="sm" data-testid={`merge-duplicate-date-${result.row}`} onClick={() => mergeDuplicateDateRows(index)}>Merge same employee/date rows into intervals</Button>}
                        {result.code === 'missing_shift' && canAssignShift && <div className="flex flex-wrap items-end gap-2 rounded border border-amber-300 p-2">
                          <p className="w-full text-xs text-muted-foreground">No effective shift covers this work date. Assigning one is a separate audited change and remains if this attendance import is discarded.</p>
                          {!shiftOptions.length ? <Button type="button" variant="outline" size="sm" onClick={loadShiftOptions} disabled={loadingShifts}>{loadingShifts ? 'Loading shifts…' : 'Load shifts'}</Button> : <>
                            <label className="grid gap-1 text-xs">Shift<select aria-label={`Assign shift for row ${result.row}`} value={assignShiftByRow[index] ?? ''} onChange={event => setAssignShiftByRow(current => ({ ...current, [index]: event.target.value }))} className="h-9 rounded border bg-background px-2"><option value="">Select shift</option>{shiftOptions.map(shift => <option key={shift.id} value={shift.id}>{shift.name} ({shift.code})</option>)}</select></label>
                            <Button type="button" size="sm" variant="outline" disabled={!assignShiftByRow[index]} onClick={() => assignShiftForRow(index)}>Confirm shift assignment</Button>
                          </>}
                        </div>}
                      </article>
                    })}
                    {correctionResults.length === 0 && <p className="text-sm text-muted-foreground">No failed rows match this filter.</p>}
                  </div>
                </section>
              )}
              <div className="max-h-48 overflow-y-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="p-2 text-left">Row</th>
                      <th className="p-2 text-left">Status</th>
                      <th className="p-2 text-left">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result, i) => (
                      <tr key={i} className="border-t">
                        <td className="p-2">{result.row}</td>
                        <td className="p-2" data-testid={`csv-row-status-${result.row}`}>
                          {result.status === 'success' ? (
                            <span className="flex items-center gap-1 text-green-600"><CheckCircle2 className="h-4 w-4" /> Success</span>
                          ) : result.status === 'unknown' ? (
                            <span className="flex items-center gap-1 text-amber-600"><AlertTriangle className="h-4 w-4" /> Unknown</span>
                          ) : (
                            <span className="flex items-center gap-1 text-destructive"><XCircle className="h-4 w-4" /> Failed</span>
                          )}
                        </td>
                        <td className="p-2 text-destructive">{result.error || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          {unknownCount > 0 && !isImporting && (
            <>
              <Button
                variant="secondary"
                onClick={handleReconcile}
                disabled={isReconciling}
                data-testid="csv-import-reconcile-button"
              >
                {isReconciling ? 'Reconciling...' : 'Reconcile'}
              </Button>
              <Button
                variant="outline"
                onClick={handleDiscard}
                disabled={isReconciling}
                className="text-destructive"
                data-testid="csv-import-discard-button"
              >
                Discard
              </Button>
            </>
          )}
          <Button variant="outline" onClick={handleClose} disabled={isImporting} data-testid="csv-import-close-button">
            Close
          </Button>
          <Button
            onClick={handleImport}
            disabled={
              isImporting ||
              parsedRows.length === 0 ||
              unknownCount > 0 ||
              results.some(row => row.retryable === false) ||
              (results.length > 0 && pendingIndices.length === 0)
            }
            data-testid="csv-import-submit-button"
          >
            <Upload className="mr-2 h-4 w-4" />
            {isImporting
              ? 'Importing...'
              : results.length === 0
                ? `Import ${parsedRows.length} Records`
                : `Retry ${pendingIndices.length} Records`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
