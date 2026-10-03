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
}

interface RecoverableBatch {
  batchId: string
  csvText: string
  headers: string[]
  rows: CsvRow[]
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
  const [headers, setHeaders] = useState<string[]>(() => restored?.headers ?? [])
  const [batchId, setBatchId] = useState(() => restored?.batchId ?? '')
  const [results, setResults] = useState<RowResult[]>(() => restored?.results ?? [])
  const [isImporting, setIsImporting] = useState(false)
  const [isReconciling, setIsReconciling] = useState(false)
  const [progress, setProgress] = useState(0)
  const [abandoned, setAbandoned] = useState(false)

  // Defense in depth: a slot owned by a DIFFERENT session is dropped on the
  // spot — it can never be restored, reconciled or retried by this account.
  useEffect(() => {
    if (recoverableSlot && recoverableSlot.owner !== owner) recoverableSlot = null
  }, [owner])

  const requiredFields = useMemo(() => DTR_REQUIRED_FIELDS, [])

  const keyForRow = useCallback(
    (index: number) => `dtr-import-${batchId}-r${index}`,
    [batchId],
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

    const rows = parsed.data
    const cols = parsed.meta.fields ?? []

    setParsedRows(rows)
    setHeaders(cols)
    setBatchId(Math.random().toString(36).slice(2, 10))
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
      setHeaders([])
      setBatchId('')
      setResults([])
    }
  }, [parseCsv, editingBlocked])

  const mapColumns = (row: CsvRow, sourceRef: string) => ({
    employee_code: row.employee_code,
    login_date: row.login_date,
    logout_date: row.logout_date,
    shift_code: row.shift_code || undefined,
    source_ref: sourceRef,
  })

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
        .filter((i) => results.length === 0 || results[i]?.status !== 'success'),
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
    setHeaders([])
    setBatchId('')
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
    if (unknownCount > 0) return // guarded in the UI; defense in depth
    if (!identityLive()) { abandonInstance(); return }

    setIsImporting(true)

    const current: RowResult[] = results.length
      ? results.map((r) => ({ ...r }))
      : parsedRows.map((row, i) => ({ row: i + 2, data: row, key: keyForRow(i), status: 'pending' as ImportStatus }))

    const total = pendingIndices.length
    let done = 0

    for (const i of pendingIndices) {
      if (!identityLive()) { abandonInstance(); return }
      const row = parsedRows[i]
      const key = current[i].key
      const validationError = validateRow(row)

      if (validationError) {
        current[i] = { ...current[i], status: 'error', error: validationError }
      } else {
        try {
          const mapped = mapColumns(row, key)
          // 201 = first create; 200 = idempotent replay of a committed row.
          await api.post('/daily-time-records', mapped)
          current[i] = { ...current[i], status: 'success', error: undefined }
        } catch (err) {
          const response = (err as { response?: { status?: number; data?: { detail?: string; error?: { message?: string } } } })?.response
          const status = response?.status
          if (status !== undefined && status >= 400 && status < 500) {
            // Definite server rejection: validation/permission/conflict — the
            // row was NOT committed; safe to correct and retry (the retry
            // keeps the same key — duplicate-safe regardless).
            const message = response?.data?.error?.message ?? response?.data?.detail ?? `Server responded ${status}`
            current[i] = { ...current[i], status: 'error', error: message }
          } else if (status !== undefined && status >= 500) {
            // Ambiguous: the server MAY have committed before failing to
            // answer. Never assume non-commit just because an error body
            // exists — treat like a lost response.
            current[i] = {
              ...current[i],
              status: 'unknown',
              error: `Server error ${status} — outcome unknown (may be recorded). Use Reconcile before retrying.`,
            }
          } else {
            // Transport failure / timeout: no server verdict at all.
            current[i] = {
              ...current[i],
              status: 'unknown',
              error: 'No response received — record may exist. Use Reconcile before retrying.',
            }
          }
        }
      }

      done += 1
      setProgress(Math.round((done / total) * 100))
    }

    // Final identity check before committing any results: if the account
    // changed mid-import, verdicts from the previous account's session are
    // never rendered and never stored for restore.
    if (!identityLive()) { abandonInstance(); return }

    if (current.some(row => row.status === 'success')) {
      await queryClient.invalidateQueries({ queryKey: ['daily-time-records'] })
    }
    setResults(current)
    setIsImporting(false)

    const successCount = current.filter(r => r.status === 'success').length
    const errorCount = current.filter(r => r.status === 'error').length
    const unresolved = current.filter(r => r.status === 'unknown').length

    if (unresolved > 0) {
      toast.error(`Imported ${successCount} time records, ${errorCount} failed, ${unresolved} awaiting reconciliation`)
    } else if (errorCount === 0) {
      toast.success(`Successfully imported ${successCount} time records`)
    } else {
      toast.error(`Imported ${successCount} time records, ${errorCount} failed`)
    }
  }, [parsedRows, results, pendingIndices, unknownCount, validateRow, queryClient, keyForRow, identityLive, abandonInstance])

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
        batch: { batchId, csvText, headers, rows: parsedRows, results },
      }
    } else if (live) {
      recoverableSlot = null
      setTimeout(() => {
        setFile(null)
        setCsvText('')
        setParsedRows([])
        setHeaders([])
        setBatchId('')
        setResults([])
        setProgress(0)
      }, 200)
    }
    onOpenChange(false)
  }, [isImporting, results, parsedRows, batchId, csvText, headers, onOpenChange, identityLive, owner])

  const successCount = results.filter(r => r.status === 'success').length
  const errorCount = results.filter(r => r.status === 'error').length

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
                <Button variant="ghost" size="icon" onClick={() => { setFile(null); setCsvText(''); setParsedRows([]); setHeaders([]); }}>
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
