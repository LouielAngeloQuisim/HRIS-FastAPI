import { AttendanceCsvImportWizard } from '@/features/attendance/components/csv-import/attendance-csv-wizard'
import { DailyTimeRecordForm } from './components/daily-time-record-form'
import { ResourceDeleteDialog } from '@/components/resource-delete-dialog'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { DailyTimeRecordPublic } from '@/lib/api/types'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useDailyTimeRecords, useApproveOvertime, useRejectOvertime, useDeleteDailyTimeRecord } from '@/lib/api/daily-time-records'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

export default function DailyTimeRecordsPage() {
  const [page] = useState(1)
  const pageSize = 50
  const canView = useCan('daily_time_record', 'view')
  const canEdit = useCan('daily_time_record', 'edit')
  const canAdd = useCan('daily_time_record', 'add')
  const canDelete = useCan('daily_time_record', 'delete')
  const [importOpen, setImportOpen] = useState(false)
  const [editing, setEditing] = useState<DailyTimeRecordPublic | null>(null)
  const [deleting, setDeleting] = useState<DailyTimeRecordPublic | null>(null)
  const [deleteError, setDeleteError] = useState<{ message: string } | null>(null)
  const deleteMutation = useDeleteDailyTimeRecord()
  const handleDelete = async () => {
    if (!deleting) return
    setDeleteError(null)
    try { await deleteMutation.mutateAsync(deleting.id); setDeleting(null) }
    catch (error) { setDeleteError({ message: saveErrorMessage(error) }) }
  }

  const { data, isPending, isError, refetch } = useDailyTimeRecords(page, pageSize)

  const approveOvertimeMutation = useApproveOvertime()
  const rejectOvertimeMutation = useRejectOvertime()

  const handleApproveOvertime = async (id: string) => {
    try {
      await approveOvertimeMutation.mutateAsync(id)
      toast.success('Overtime approved')
    } catch {
      toast.error('Failed to approve overtime')
    }
  }

  const handleRejectOvertime = async (id: string) => {
    try {
      await rejectOvertimeMutation.mutateAsync(id)
      toast.success('Overtime rejected')
    } catch {
      toast.error('Failed to reject overtime')
    }
  }

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
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load daily time records.</p>
          <button data-testid="retry-button" type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
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
                  <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2">{item.employee_id ?? '—'}</td>
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
                                 onClick={() => handleApproveOvertime(item.id)}
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
                            <span className="text-xs text-green-600">✓</span>
                          )}
                          {item.overtime_approved === false && (
                            <span className="text-xs text-red-600">✗</span>
                          )}
                        </div>
                      ) : '—'}
                    </td>
                    <td className="p-2 text-center">{item.is_absent ? 'Yes' : 'No'}</td>
                    <td className="p-2">{item.source ?? '—'}</td>
                    {(canEdit || canDelete) && (
                      <td className="p-2 text-right">
                        {canEdit && <Button data-testid={`edit-daily-time-record-button-${item.id}`} variant="ghost" size="sm" onClick={() => setEditing(item)}>Edit</Button>}
                        {canDelete && <Button data-testid={`delete-daily-time-record-button-${item.id}`} variant="ghost" size="sm" onClick={() => { setDeleteError(null); setDeleting(item) }}>Delete</Button>}
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
      {importOpen && <AttendanceCsvImportWizard open={importOpen} onOpenChange={setImportOpen} />}
      {editing && <DailyTimeRecordForm key={editing.id} item={editing} open onClose={() => setEditing(null)} />}
      <ResourceDeleteDialog open={Boolean(deleting)} onOpenChange={value => { if (!value) setDeleting(null) }} entityName="Daily Time Record" entityLabel={deleting?.login_date ?? ''} onConfirm={handleDelete} isPending={deleteMutation.isPending} conflictError={deleteError} />
    </div>
  )
}
