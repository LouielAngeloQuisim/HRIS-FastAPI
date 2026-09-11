import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useLeaveLedger } from '@/lib/api/leave-ledger'
import { Button } from '@/components/ui/button'

export default function LeaveLedgerPage() {
  const [employeeId] = useState('00000000-0000-0000-0000-000000000000')
  const [policyId] = useState<string | undefined>(undefined)
  const [leaveYear, setLeaveYear] = useState(new Date().getFullYear())
  const canView = useCan('emp_leaves', 'view')

  const { data, isPending, isError, refetch } = useLeaveLedger(employeeId, policyId, leaveYear)

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view leave ledger.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Leave Ledger</h1>
          <p className="text-muted-foreground">
            Granted: {data?.summary?.granted_total ?? 0} | Consumed: {data?.summary?.consumed_total ?? 0} | Remaining: {data?.summary?.remaining ?? 0}
          </p>
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            className="border rounded px-2 py-1 text-sm w-24"
            value={leaveYear}
            onChange={(e) => setLeaveYear(Number(e.target.value))}
            data-testid="leave-ledger-year-input"
          />
          <Button onClick={() => refetch()} data-testid="leave-ledger-refresh-button">Refresh</Button>
        </div>
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load leave ledger.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {!isPending && !isError && (!data || data.data.length === 0) && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Date</th>
                <th className="p-2 text-left">Source</th>
                <th className="p-2 text-right">Amount</th>
                <th className="p-2 text-left">Reference</th>
                <th className="p-2 text-left">Note</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colSpan={5} className="p-4 text-center text-muted-foreground">No ledger entries found.</td></tr>
            </tbody>
          </table>
        </div>
      )}
      {data && data.data.length > 0 && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Date</th>
                <th className="p-2 text-left">Source</th>
                <th className="p-2 text-right">Amount</th>
                <th className="p-2 text-left">Reference</th>
                <th className="p-2 text-left">Note</th>
              </tr>
            </thead>
            <tbody>
              {data.data.length === 0 ? (
                <tr><td colSpan={5} className="p-4 text-center text-muted-foreground">No ledger entries found.</td></tr>
              ) : (
                data.data.map((item) => (
                  <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2">{item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}</td>
                    <td className="p-2 capitalize">{item.source.replace(/_/g, ' ')}</td>
                    <td className={`p-2 text-right font-medium ${item.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {item.amount > 0 ? '+' : ''}{item.amount}
                    </td>
                    <td className="p-2">{item.reference ?? '—'}</td>
                    <td className="p-2">{item.note ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
