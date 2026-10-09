import { relationshipLabel, useRelationshipLabels } from '@/lib/api/relationship-labels'
import { AttendanceCsvImportWizard } from '@/features/attendance/components/csv-import/attendance-csv-wizard'
import { DailyTimeRecordForm } from './components/daily-time-record-form'
import { ResourceDeleteDialog } from '@/components/resource-delete-dialog'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { DailyTimeRecordPublic } from '@/lib/api/types'
import { Fragment, useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useDailyTimeRecords, useApproveOvertime, useRejectOvertime, useDeleteDailyTimeRecord } from '@/lib/api/daily-time-records'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { DtrIntervalsEditor } from './components/dtr-intervals-editor'

export default function DailyTimeRecordsPage() {
  const [page] = useState(1)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [employeeCode, setEmployeeCode] = useState('')
  const [calendarView, setCalendarView] = useState<'table' | 'month' | 'week' | 'day'>('table')
  const [calendarDate, setCalendarDate] = useState(() => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' }))
  const pageSize = 500
  const canView = useCan('daily_time_record', 'view')
  const canEdit = useCan('daily_time_record', 'edit')
  const canAdd = useCan('daily_time_record', 'add')
  const canDelete = useCan('daily_time_record', 'delete')
  const [importOpen, setImportOpen] = useState(false)
  const [editing, setEditing] = useState<DailyTimeRecordPublic | null>(null)
  const [deleting, setDeleting] = useState<DailyTimeRecordPublic | null>(null)
  const [deleteError, setDeleteError] = useState<{ message: string } | null>(null)
  const [intervalRecordId, setIntervalRecordId] = useState<string | null>(null)
  const deleteMutation = useDeleteDailyTimeRecord()
  const handleDelete = async () => {
    if (!deleting) return
    setDeleteError(null)
    try { await deleteMutation.mutateAsync(deleting.id); setDeleting(null) }
    catch (error) { setDeleteError({ message: saveErrorMessage(error) }) }
  }

  const [year, month, day] = calendarDate.split('-').map(Number)
  const selectedUtc = new Date(Date.UTC(year, month - 1, day))
  const monthStart = new Date(Date.UTC(year, month - 1, 1))
  const monthDayCount = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const mondayOffset = (selectedUtc.getUTCDay() + 6) % 7
  const weekStart = new Date(selectedUtc)
  weekStart.setUTCDate(weekStart.getUTCDate() - mondayOffset)
  const rangeStart = calendarView === 'month'
    ? `${year}-${String(month).padStart(2, '0')}-01`
    : calendarView === 'week'
      ? weekStart.toISOString().slice(0, 10)
      : calendarView === 'day' ? calendarDate : (dateFrom || undefined)
  const rangeEnd = calendarView === 'month'
    ? `${year}-${String(month).padStart(2, '0')}-${String(monthDayCount).padStart(2, '0')}`
    : calendarView === 'week'
      ? new Date(weekStart.getTime() + 6 * 86400000).toISOString().slice(0, 10)
      : calendarView === 'day' ? calendarDate : (dateTo || undefined)

  const { data, isPending, isError, refetch } = useDailyTimeRecords(
    page,
    pageSize,
    undefined,
    rangeStart,
    rangeEnd,
    employeeCode.trim() || undefined,
  )

  const approveOvertimeMutation = useApproveOvertime()
  const rejectOvertimeMutation = useRejectOvertime()

  const handleApproveOvertime = async (item: DailyTimeRecordPublic) => {
    const enteredMinutes = window.prompt(
      `Eligible overtime is ${item.overtime_minutes} minutes. How many minutes should be approved?`,
      String(item.overtime_minutes),
    )
    if (enteredMinutes === null) return
    const approved_minutes = Number(enteredMinutes)
    if (!Number.isInteger(approved_minutes) || approved_minutes <= 0 || approved_minutes > (item.overtime_minutes ?? 0)) {
      toast.error('Enter a whole number of minutes within the eligible overtime.')
      return
    }
    const reason = window.prompt('Reason for approving this overtime:')
    if (!reason?.trim()) return
    try {
      await approveOvertimeMutation.mutateAsync({ id: item.id, approved_minutes, reason: reason.trim() })
      toast.success('Overtime approved')
    } catch {
      toast.error('Failed to approve overtime')
    }
  }

  const handleRejectOvertime = async (id: string) => {
    const reason = window.prompt('Reason for rejecting this overtime:')
    if (!reason?.trim()) return
    try {
      await rejectOvertimeMutation.mutateAsync({ id, reason: reason.trim() })
      toast.success('Overtime rejected')
    } catch {
      toast.error('Failed to reject overtime')
    }
  }

  const employee_idLabels = useRelationshipLabels('employees', (data?.data ?? []).map(item => item.employee_id))
  const calendarDates = calendarView === 'month'
    ? Array.from({ length: ((monthStart.getUTCDay() + 6) % 7) + monthDayCount }, (_, index) => {
      const dayNumber = index - ((monthStart.getUTCDay() + 6) % 7) + 1
      return dayNumber < 1 || dayNumber > monthDayCount ? null : `${year}-${String(month).padStart(2, '0')}-${String(dayNumber).padStart(2, '0')}`
    })
    : calendarView === 'week'
      ? Array.from({ length: 7 }, (_, index) => new Date(weekStart.getTime() + index * 86400000).toISOString().slice(0, 10))
      : calendarView === 'day' ? [calendarDate] : []

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view daily time records.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Daily Time Records</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
        {canAdd && <Button onClick={() => setImportOpen(true)} data-testid="import-dtr-csv-button">Import CSV</Button>}
      </div>
      <div className="flex flex-wrap items-end gap-3 rounded-md border p-3" aria-label="Attendance filters">
        <label className="grid gap-1 text-sm"><span>View</span><select aria-label="Calendar view" value={calendarView} onChange={event => setCalendarView(event.target.value as typeof calendarView)} className="h-9 rounded border bg-background px-3"><option value="table">Table</option><option value="month">Month</option><option value="week">Week</option><option value="day">Day</option></select></label>
        {calendarView !== 'table' && <label className="grid gap-1 text-sm"><span>Calendar date</span><input aria-label="Calendar date" type="date" value={calendarDate} onChange={event => setCalendarDate(event.target.value)} className="h-9 rounded border bg-background px-3" /></label>}
        <label className="grid gap-1 text-sm">
          <span>Employee code</span>
          <input
            className="h-9 w-44 rounded-md border bg-background px-3"
            value={employeeCode}
            onChange={event => setEmployeeCode(event.target.value)}
            placeholder="All employees"
            aria-label="Filter by employee code"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span>Work date from</span>
          <input
            type="date"
            className="h-9 rounded-md border bg-background px-3"
            value={dateFrom}
            onChange={event => setDateFrom(event.target.value)}
            aria-label="Filter from date"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span>Work date to</span>
          <input
            type="date"
            className="h-9 rounded-md border bg-background px-3"
            value={dateTo}
            onChange={event => setDateTo(event.target.value)}
            aria-label="Filter to date"
          />
        </label>
        {(employeeCode || dateFrom || dateTo) && (
          <Button
            variant="outline"
            onClick={() => { setEmployeeCode(''); setDateFrom(''); setDateTo('') }}
          >
            Clear filters
          </Button>
        )}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load daily time records.</p>
          <button data-testid="retry-button" type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <>
        {data.count > data.data.length && <p className="text-xs text-amber-700">Showing {data.data.length} of {data.count} matching records. Narrow the employee or date filter for a complete calendar view.</p>}
        {calendarView === 'month' && <div className="grid grid-cols-7 gap-2 text-xs text-muted-foreground">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(label => <span key={label} className="p-2">{label}</span>)}</div>}
        {calendarView !== 'table' && <div className={`grid gap-2 ${calendarView === 'month' ? 'grid-cols-7' : 'grid-cols-1 md:grid-cols-7'}`} aria-label={`${calendarView} attendance calendar`}>
          {calendarDates.map((date, index) => date ? <section key={date} className="min-h-24 rounded border p-2" data-testid={`attendance-calendar-day-${date}`}><h2 className="text-xs font-semibold">{date}</h2>{(data.data ?? []).filter(item => (item.work_date ?? item.login_date?.slice(0, 10)) === date).map(item => <div key={item.id} className="mt-1 truncate text-xs" title={`${relationshipLabel(employee_idLabels.data, item.employee_id)} ${item.login_date ?? ''}–${item.logout_date ?? ''}`}><p>{relationshipLabel(employee_idLabels.data, item.employee_id)} · {item.rendered_minutes ?? '—'} min</p><p className="text-muted-foreground">Late {item.late_minutes ?? 0}m · OT {item.overtime_minutes ?? 0}m {item.overtime_minutes ? (item.overtime_approved === null ? 'pending' : item.overtime_approved ? 'approved' : 'rejected') : ''}</p></div>)}</section> : <div key={`empty-${index}`} aria-hidden="true" />)}
        </div>}
        {calendarView === 'table' && <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Employee ID</th>
                <th className="p-2 text-left">Login Date</th>
                <th className="p-2 text-left">Logout Date</th>
                <th className="p-2 text-right">Rendered (min)</th>
                <th className="p-2 text-right">Late (min)</th>
                <th className="p-2 text-right">Undertime (min)</th>
                <th className="p-2 text-right">OT (min)</th>
                <th className="p-2 text-center">Absent</th>
                <th className="p-2 text-left">Source</th>
                {(canEdit || canDelete) && <th className="p-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.data.length === 0 ? (
                <tr><td colSpan={10} className="p-4 text-center text-muted-foreground">No records found.</td></tr>
              ) : (
                data.data.map((item) => (
                  <Fragment key={item.id}>
                  <tr className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2">{relationshipLabel(employee_idLabels.data, item.employee_id)}</td>
                    <td className="p-2">{item.login_date ? new Date(item.login_date).toLocaleString() : '—'}</td>
                    <td className="p-2">{item.logout_date ? new Date(item.logout_date).toLocaleString() : '—'}</td>
                    <td className="p-2 text-right">{item.rendered_minutes ?? '—'}</td>
                    <td className="p-2 text-right">{item.late_minutes ?? '—'}</td>
                    <td className="p-2 text-right">{item.undertime_minutes ?? '—'}</td>
                    <td className="p-2 text-right">
                      {item.overtime_minutes != null ? (
                        <div className="flex items-center justify-end gap-1">
                          <span>{item.overtime_minutes}</span>
                          {item.overtime_minutes > 0 && item.overtime_approved === null && canEdit && (
                            <div className="flex gap-1">
                               <Button
                                 data-testid={`approve-overtime-button-${item.id}`}
                                 variant="ghost"
                                 size="sm"
                                 className="h-5 px-1 text-xs"
                                 onClick={() => handleApproveOvertime(item)}
                                 disabled={approveOvertimeMutation.isPending}
                               >
                                 ✓
                               </Button>
                               <Button
                                 data-testid={`reject-overtime-button-${item.id}`}
                                 variant="ghost"
                                 size="sm"
                                 className="h-5 px-1 text-xs text-destructive"
                                 onClick={() => handleRejectOvertime(item.id)}
                                 disabled={rejectOvertimeMutation.isPending}
                               >
                                 ✗
                               </Button>
                            </div>
                          )}
                          {item.overtime_approved === true && (
                            <span className="text-xs text-green-600" title={item.overtime_decision_reason ?? undefined}>✓ {item.overtime_approved_minutes ?? item.overtime_minutes}</span>
                          )}
                          {item.overtime_approved === false && (
                            <span className="text-xs text-red-600" title={item.overtime_decision_reason ?? undefined}>✗</span>
                          )}
                        </div>
                      ) : '—'}
                    </td>
                    <td className="p-2 text-center">{item.is_absent ? 'Yes' : 'No'}</td>
                    <td className="p-2">{item.source ?? '—'}</td>
                    {(canEdit || canDelete) && (
                      <td className="p-2 text-right">
                        {canEdit && <Button data-testid={`edit-dtr-intervals-button-${item.id}`} variant="ghost" size="sm" onClick={() => setIntervalRecordId(intervalRecordId === item.id ? null : item.id)}>{intervalRecordId === item.id ? 'Hide intervals' : 'Intervals'}</Button>}
                        {canEdit && <Button data-testid={`edit-daily-time-record-button-${item.id}`} variant="ghost" size="sm" onClick={() => setEditing(item)}>Edit</Button>}
                        {canDelete && <Button data-testid={`delete-daily-time-record-button-${item.id}`} variant="ghost" size="sm" onClick={() => { setDeleteError(null); setDeleting(item) }}>Delete</Button>}
                      </td>
                    )}
                  </tr>
                  {intervalRecordId === item.id && <tr><td colSpan={10}><DtrIntervalsEditor record={item} onClose={() => setIntervalRecordId(null)} /></td></tr>}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>}
        </>
      )}
      {importOpen && <AttendanceCsvImportWizard open={importOpen} onOpenChange={setImportOpen} />}
      {editing && <DailyTimeRecordForm key={editing.id} item={editing} open onClose={() => setEditing(null)} />}
      <ResourceDeleteDialog open={Boolean(deleting)} onOpenChange={value => { if (!value) setDeleting(null) }} entityName="Daily Time Record" entityLabel={deleting?.login_date ?? ''} onConfirm={handleDelete} isPending={deleteMutation.isPending} conflictError={deleteError} />
    </div>
  )
}
