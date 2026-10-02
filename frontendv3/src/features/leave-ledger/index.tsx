import { useLeavePolicies } from '@/lib/api/leave-policies'
import { useEmployees } from '@/lib/api/employees'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useLeaveLedger } from '@/lib/api/leave-ledger'
import { Button } from '@/components/ui/button'

export default function LeaveLedgerPage() {
  const [employeeId, setEmployeeId] = useState('')
  const employees = useEmployees(1, 100)
  const [policyId, setPolicyId] = useState('')
  const policies = useLeavePolicies()
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
            aria-label="Leave Year"
            type="number"
            className="border rounded px-2 py-1 text-sm w-24"
            value={leaveYear}
            onChange={(e) => setLeaveYear(Number(e.target.value))}
            data-testid="leave-ledger-year-input"
          />
          <Button disabled={!employeeId || !policyId} onClick={() => refetch()} data-testid="leave-ledger-refresh-button">Refresh</Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="leave-ledger-employee">Employee</label>
        <select id="leave-ledger-employee" data-testid="leave-ledger-employee-select" className="rounded border bg-background p-2" value={employeeId} onChange={event => setEmployeeId(event.target.value)}>
          <option value="">Select an employee</option>
          {(employees.data?.data ?? []).map(employee => <option key={employee.id} value={employee.id}>{employee.employee_code} - {employee.first_name} {employee.last_name}</option>)}
        </select>
        <label htmlFor="leave-ledger-policy">Policy</label>
        <select id="leave-ledger-policy" data-testid="leave-ledger-policy-select" className="rounded border bg-background p-2" value={policyId} onChange={event => setPolicyId(event.target.value)}>
          <option value="">Select a policy</option>
          {(policies.data?.data ?? []).filter(policy => policy.is_active).map(policy => <option key={policy.id} value={policy.id}>{policy.code} - {policy.name}</option>)}
        </select>
      </div>
      {!employeeId && <p>Select an employee to view their leave ledger.</p>}
      {employeeId && !policyId && <p>Select a leave policy to view its ledger.</p>}
      {employeeId && policyId && isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {employeeId && policyId && isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load leave ledger.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {employeeId && policyId && !isPending && !isError && (!data || data.data.length === 0) && (
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
      {employeeId && policyId && data && data.data.length > 0 && (
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
