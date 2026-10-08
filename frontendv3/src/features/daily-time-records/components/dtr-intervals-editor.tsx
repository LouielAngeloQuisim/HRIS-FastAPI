import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { DailyTimeRecordPublic } from '@/lib/api/types'
import { useDtrIntervals, useReplaceDtrIntervals, type DtrIntervalInput } from '@/lib/api/daily-time-records'
import { toast } from 'sonner'

type DraftInterval = { start: string; end: string }

function toManilaInput(value: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(value))
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${values['year']}-${values['month']}-${values['day']}T${values['hour']}:${values['minute']}`
}

function fromManilaInput(value: string): string {
  return new Date(`${value}:00+08:00`).toISOString()
}

export function DtrIntervalsEditor({ record, onClose }: { record: DailyTimeRecordPublic; onClose: () => void }) {
  const query = useDtrIntervals(record.id)
  const mutation = useReplaceDtrIntervals(record.id)
  const initialDrafts = query.data?.length
    ? query.data.map(item => ({ start: toManilaInput(item.start_at), end: toManilaInput(item.end_at) }))
    : record.login_date && record.logout_date
      ? [{ start: toManilaInput(record.login_date), end: toManilaInput(record.logout_date) }]
      : []
  const [draftsOverride, setDraftsOverride] = useState<DraftInterval[] | null>(null)
  const drafts = draftsOverride ?? initialDrafts
  const [historyOpen, setHistoryOpen] = useState(false)
  const historyQuery = useDtrIntervals(record.id, true, historyOpen)

  const save = async () => {
    const intervals: DtrIntervalInput[] = drafts.map(item => ({
      start_at: fromManilaInput(item.start),
      end_at: fromManilaInput(item.end),
      original_row: { login_date: item.start, logout_date: item.end, source: 'attendance_interval_correction' },
    }))
    try {
      await mutation.mutateAsync(intervals)
      toast.success('Attendance intervals saved; overtime review was reset for this new revision.')
      onClose()
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Could not save intervals. Check for overlapping times and the assigned shift.')
    }
  }

  if (query.isPending) return <div className="border-t p-3 text-sm">Loading interval history…</div>
  if (query.isError) return <div className="border-t p-3 text-sm text-destructive">Could not load intervals. Close and retry.</div>

  return (
    <div className="space-y-3 border-t bg-muted/20 p-3" data-testid={`dtr-interval-editor-${record.id}`}>
      <div className="flex items-center justify-between gap-2">
        <div><h3 className="font-medium">Work intervals</h3><p className="text-xs text-muted-foreground">Times use Asia/Manila. The assigned shift break is deducted once from total punch time. Each save creates an auditable revision; overlaps are rejected.</p></div>
        <div className="flex gap-2"><Button type="button" variant="outline" size="sm" onClick={() => setHistoryOpen(value => !value)}>{historyOpen ? 'Hide history' : 'View history'}</Button><Button type="button" variant="outline" size="sm" disabled={drafts.length >= 20} onClick={() => setDraftsOverride(current => [...(current ?? initialDrafts), { start: '', end: '' }])}>Add interval</Button></div>
      </div>
      {historyOpen && <div className="rounded border p-2 text-xs" data-testid={`dtr-interval-history-${record.id}`}>
        {historyQuery.isPending ? 'Loading history…' : historyQuery.isError ? 'Could not load interval history.' : historyQuery.data?.length ? [...new Set(historyQuery.data.map(item => item.revision))].sort((a, b) => b - a).map(revision => <p key={revision}>Revision {revision}: {historyQuery.data?.filter(item => item.revision === revision).map(item => `${toManilaInput(item.start_at)}–${toManilaInput(item.end_at)}`).join(', ')}</p>) : 'No saved interval revisions yet.'}
      </div>}
      {drafts.map((item, index) => <div key={index} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <label className="grid gap-1 text-xs">Start<input type="datetime-local" value={item.start} onChange={event => setDraftsOverride(rows => (rows ?? initialDrafts).map((row, i) => i === index ? { ...row, start: event.target.value } : row))} className="h-9 rounded border bg-background px-2" /></label>
        <label className="grid gap-1 text-xs">End<input type="datetime-local" value={item.end} onChange={event => setDraftsOverride(rows => (rows ?? initialDrafts).map((row, i) => i === index ? { ...row, end: event.target.value } : row))} className="h-9 rounded border bg-background px-2" /></label>
        <Button type="button" variant="ghost" size="sm" disabled={drafts.length <= 1} onClick={() => setDraftsOverride(rows => (rows ?? initialDrafts).filter((_, i) => i !== index))}>Remove</Button>
      </div>)}
      <div className="flex gap-2"><Button type="button" onClick={save} disabled={mutation.isPending || drafts.some(item => !item.start || !item.end)}>Save intervals</Button><Button type="button" variant="outline" onClick={onClose}>Cancel</Button></div>
    </div>
  )
}
