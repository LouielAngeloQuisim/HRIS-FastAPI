import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useDtrAdjustments, useApproveDtrAdjustment, useRejectDtrAdjustment } from '@/lib/api/dtr-adjustments'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { DtrAdjustmentForm } from './components/dtr-adjustment-form'

export default function DtrAdjustmentsPage() {
  const [page] = useState(1)
  const pageSize = 50
  const canView = useCan('daily_time_record', 'view')
  const canEdit = useCan('daily_time_record', 'edit')
  const [open, setOpen] = useState(false)

  const { data, isPending, isError, refetch } = useDtrAdjustments(page, pageSize)

  const approveMutation = useApproveDtrAdjustment()
  const rejectMutation = useRejectDtrAdjustment()

  const handleApprove = async (id: string) => {
    try {
      await approveMutation.mutateAsync(id)
      toast.success('DTR adjustment approved')
    } catch {
      toast.error('Failed to approve DTR adjustment')
    }
  }

  const handleReject = async (id: string) => {
    try {
      await rejectMutation.mutateAsync(id)
      toast.success('DTR adjustment rejected')
    } catch {
      toast.error('Failed to reject DTR adjustment')
    }
  }

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view DTR adjustments.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">DTR Adjustments</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
        {canEdit && (
          <Button data-testid="new-dtr-adjustment-button" onClick={() => setOpen(true)}>New Adjustment</Button>
        )}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load DTR adjustments.</p>
          <button data-testid="retry-button" type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Employee ID</th>
                <th className="p-2 text-left">Original Login</th>
                <th className="p-2 text-left">Original Logout</th>
                <th className="p-2 text-left">Adjusted Login</th>
                <th className="p-2 text-left">Adjusted Logout</th>
                <th className="p-2 text-left">Status</th>
                <th className="p-2 text-left">Reason</th>
                {canEdit && <th className="p-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.data.length === 0 ? (
                <tr><td colSpan={8} className="p-4 text-center text-muted-foreground">No records found.</td></tr>
              ) : (
                data.data.map((item) => (
                  <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2">{item.employee_id ?? '—'}</td>
                    <td className="p-2">{item.original_login_date ? new Date(item.original_login_date).toLocaleString() : '—'}</td>
                    <td className="p-2">{item.original_logout_date ? new Date(item.original_logout_date).toLocaleString() : '—'}</td>
                    <td className="p-2">{item.adjusted_login_date ? new Date(item.adjusted_login_date).toLocaleString() : '—'}</td>
                    <td className="p-2">{item.adjusted_logout_date ? new Date(item.adjusted_logout_date).toLocaleString() : '—'}</td>
                    <td className="p-2">
                      <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${
                        item.status === 'approved' ? 'bg-green-100 text-green-800' :
                        item.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                        item.status === 'rejected' ? 'bg-red-100 text-red-800' : ''
                      }`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="p-2 max-w-xs truncate">{item.reason ?? '—'}</td>
                    {canEdit && (
                      <td className="p-2 text-right">
                        {item.status === 'pending' && (
                          <div className="flex gap-1 justify-end">
                             <Button
                               data-testid={`approve-dtr-adjustment-button-${item.id}`}
                               variant="ghost"
                               size="sm"
                               onClick={() => handleApprove(item.id)}
                               disabled={approveMutation.isPending}
                             >
                               Approve
                             </Button>
                             <Button
                               data-testid={`reject-dtr-adjustment-button-${item.id}`}
                               variant="ghost"
                               size="sm"
                               className="text-destructive"
                               onClick={() => handleReject(item.id)}
                               disabled={rejectMutation.isPending}
                             >
                               Reject
                             </Button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
      <DtrAdjustmentForm open={open} onClose={() => setOpen(false)} />
    </div>
  )
}
