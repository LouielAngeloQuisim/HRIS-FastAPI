import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useLeaveRequests, useApproveLeaveRequest, useRejectLeaveRequest } from '@/lib/api/leave-requests'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { LeaveRequestForm } from './components/leave-request-form'

export default function LeaveRequestsPage() {
  const [page] = useState(1)
  const pageSize = 50
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const canView = useCan('leave_request', 'view')
  const canApprove = useCan('leave_request', 'approve')
  const [open, setOpen] = useState(false)

  const { data, isPending, isError, refetch } = useLeaveRequests(page, pageSize, { status: statusFilter })

  const approveMutation = useApproveLeaveRequest()
  const rejectMutation = useRejectLeaveRequest()

  const handleApprove = async (id: string) => {
    try {
      await approveMutation.mutateAsync(id)
      toast.success('Leave request approved')
    } catch {
      toast.error('Failed to approve leave request')
    }
  }

  const handleReject = async (id: string) => {
    try {
      await rejectMutation.mutateAsync({ id })
      toast.success('Leave request rejected')
    } catch {
      toast.error('Failed to reject leave request')
    }
  }

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view leave requests.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Leave Requests</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
        <div className="flex gap-2">
          <select
            data-testid="leave-request-status-filter"
            className="border rounded px-2 py-1 text-sm"
            value={statusFilter ?? ''}
            onChange={(e) => setStatusFilter(e.target.value || undefined)}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <Button data-testid="new-leave-request-button" onClick={() => setOpen(true)}>New Leave Request</Button>
        </div>
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load leave requests.</p>
          <button data-testid="retry-button" type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Employee ID</th>
                <th className="p-2 text-left">Policy ID</th>
                <th className="p-2 text-left">Date Start</th>
                <th className="p-2 text-left">Date End</th>
                <th className="p-2 text-right">Days</th>
                <th className="p-2 text-left">Status</th>
                <th className="p-2 text-left">Reason</th>
                {canApprove && <th className="p-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.data.length === 0 ? (
                <tr><td colSpan={8} className="p-4 text-center text-muted-foreground">No records found.</td></tr>
              ) : (
                data.data.map((item) => (
                  <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2">{item.employee_id ?? '—'}</td>
                    <td className="p-2">{item.policy_id ?? '—'}</td>
                    <td className="p-2">{item.date_start ?? '—'}</td>
                    <td className="p-2">{item.date_end ?? '—'}</td>
                    <td className="p-2 text-right">{item.total_days_requested}</td>
                    <td className="p-2">
                      <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${
                        item.status === 'approved' ? 'bg-green-100 text-green-800' :
                        item.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                        item.status === 'rejected' ? 'bg-red-100 text-red-800' :
                        item.status === 'cancelled' ? 'bg-gray-100 text-gray-800' : ''
                      }`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="p-2 max-w-xs truncate">{item.reason ?? '—'}</td>
                    {canApprove && (
                      <td className="p-2 text-right">
                        {item.status === 'pending' && (
                          <div className="flex gap-1 justify-end">
                            <Button
                              data-testid={`approve-leave-request-button-${item.id}`}
                              variant="ghost"
                              size="sm"
                              onClick={() => handleApprove(item.id)}
                              disabled={approveMutation.isPending}
                            >
                              Approve
                            </Button>
                            <Button
                              data-testid={`reject-leave-request-button-${item.id}`}
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
      <LeaveRequestForm open={open} onClose={() => setOpen(false)} />
    </div>
  )
}
