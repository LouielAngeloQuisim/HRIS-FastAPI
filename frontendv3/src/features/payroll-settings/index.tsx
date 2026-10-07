import { useState, type FormEvent } from 'react'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { usePayGroupPeriods, usePayrollSetup } from '@/lib/api/payroll'
import { useEmployees } from '@/lib/api/employees'
import { toast } from 'sonner'

export default function PayrollSettingsPage() {
  const canView = useCan('payroll', 'view')
  const canAdd = useCan('payroll', 'add')
  const canEdit = useCan('payroll', 'edit')
  const setup = usePayrollSetup()
  const employees = useEmployees(1, 500)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [cadence, setCadence] = useState<'daily' | 'semi_monthly' | 'monthly'>('semi_monthly')
  const [firstEnd, setFirstEnd] = useState('15')
  const [secondEnd, setSecondEnd] = useState('31')
  const [offset, setOffset] = useState('0')
  const [employeeId, setEmployeeId] = useState('')
  const [groupId, setGroupId] = useState('')
  const [effectiveDate, setEffectiveDate] = useState('')
  const [assignmentEndDate, setAssignmentEndDate] = useState('')
  const [policyJson, setPolicyJson] = useState(`{
  "timezone": "Asia/Manila",
  "monthly_divisor": null,
  "daily_partial_work": null,
  "paid_leave": null,
  "paid_holidays": null,
  "break_minutes": null,
  "grace_minutes": null,
  "overtime_rule": null,
  "premium_rules": null,
  "allowance_tax_treatment": null,
  "rounding_mode": null,
  "contribution_collection": null,
  "statutory_sources_reviewed": []
}`)
  const [policyEffectiveDate, setPolicyEffectiveDate] = useState('')
  const [periodGroupId, setPeriodGroupId] = useState('')
  const [periodMonth, setPeriodMonth] = useState(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit' }))
  const periods = usePayGroupPeriods(periodGroupId, periodMonth)

  if (!canView) return <p className="p-6 text-muted-foreground">You do not have permission to view payroll settings.</p>

  const submitGroup = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await setup.createGroup.mutateAsync({
        code: code.trim(), name: name.trim(), cadence,
        first_period_end_day: cadence === 'semi_monthly' ? Number(firstEnd) : null,
        second_period_end_day: cadence === 'semi_monthly' ? Number(secondEnd) : null,
        payment_offset_days: Number(offset), weekend_rule: 'next_business_day',
      })
      setCode(''); setName(''); toast.success('Pay group created')
    } catch { toast.error('Could not create pay group; check the code and period boundaries.') }
  }

  const submitAssignment = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await setup.assignGroup.mutateAsync({ employee_id: employeeId, pay_group_id: groupId, effective_from: effectiveDate, effective_to: assignmentEndDate || null })
      setEmployeeId(''); setAssignmentEndDate(''); toast.success('Pay group assignment saved')
    } catch { toast.error('Could not save assignment. Check the employee, group and effective date for conflicts.') }
  }

  const submitPolicy = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const policy = JSON.parse(policyJson) as Record<string, unknown>
      await setup.createPolicy.mutateAsync({ effective_from: policyEffectiveDate, policy })
      toast.success('Policy draft saved. It cannot be used until required rules are completed and confirmed.')
    } catch { toast.error('Policy JSON is invalid or the policy could not be saved.') }
  }

  const loadError = setup.groups.isError || setup.policies.isError || setup.assignments.isError

  return (
    <main className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold">Payroll setup</h1>
        <p className="text-muted-foreground">Define payment cadence separately from salary basis, assign employees by effective date, and version the company rules.</p>
      </header>
      {loadError && <p role="alert" className="text-destructive">Some payroll settings could not be loaded. Refresh to try again.</p>}

      <section className="space-y-3 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Pay groups</h2>
        {setup.groups.data?.map(group => <p key={group.id}>{group.name} ({group.code}) · {group.cadence.replace('_', ' ')}{group.cadence === 'semi_monthly' ? ` · period ends ${group.first_period_end_day} and ${group.second_period_end_day}` : ''}</p>)}
        {!setup.groups.isPending && !setup.groups.data?.length && <p className="text-sm text-muted-foreground">No pay groups configured.</p>}
        <div className="grid gap-2 sm:grid-cols-[1fr_180px]">
          <label className="grid gap-1 text-sm">Preview periods for group<select value={periodGroupId} onChange={e => setPeriodGroupId(e.target.value)} className="h-9 rounded border bg-background px-3"><option value="">Choose pay group</option>{setup.groups.data?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Month<input type="month" value={periodMonth} onChange={e => setPeriodMonth(e.target.value)} className="h-9 rounded border bg-background px-3" /></label>
        </div>
        {periods.data?.map(period => <p key={`${period.date_from}-${period.date_to}`} className="text-sm">Earning period {period.date_from} → {period.date_to} · scheduled payment {period.payment_date}</p>)}
        {periods.isError && <p role="alert" className="text-sm text-destructive">Could not calculate scheduled periods.</p>}
        {canAdd && <form onSubmit={submitGroup} className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1 text-sm">Code<input required maxLength={32} value={code} onChange={e => setCode(e.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <label className="grid gap-1 text-sm">Name<input required maxLength={128} value={name} onChange={e => setName(e.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <label className="grid gap-1 text-sm">Pay cadence<select value={cadence} onChange={e => setCadence(e.target.value as typeof cadence)} className="h-9 rounded border bg-background px-3"><option value="daily">Daily</option><option value="semi_monthly">Twice monthly</option><option value="monthly">Monthly</option></select></label>
          {cadence === 'semi_monthly' && <><label className="grid gap-1 text-sm">First period ends on day<input type="number" min={1} max={30} value={firstEnd} onChange={e => setFirstEnd(e.target.value)} className="h-9 rounded border bg-background px-3" /></label><label className="grid gap-1 text-sm">Second period ends on day (31 = month end)<input type="number" min={16} max={31} value={secondEnd} onChange={e => setSecondEnd(e.target.value)} className="h-9 rounded border bg-background px-3" /></label></>}
          <label className="grid gap-1 text-sm">Payment offset after period end (days)<input type="number" min={0} max={60} value={offset} onChange={e => setOffset(e.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <Button type="submit" disabled={setup.createGroup.isPending} className="w-fit">Create pay group</Button>
        </form>}
      </section>

      <section className="space-y-3 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Employee assignments</h2>
        <p className="text-sm text-muted-foreground">Assignments cannot overlap. A transfer takes effect on the date entered.</p>
        {setup.assignments.data?.map(item => <p key={item.id} className="text-sm">Employee {item.employee_id} · group {setup.groups.data?.find(g => g.id === item.pay_group_id)?.name ?? item.pay_group_id} · from {item.effective_from}{item.effective_to ? ` to ${item.effective_to}` : ''}</p>)}
        {canAdd && <form onSubmit={submitAssignment} className="grid gap-3 md:grid-cols-3">
          <label className="grid gap-1 text-sm">Employee<select required value={employeeId} onChange={e => setEmployeeId(e.target.value)} className="h-9 rounded border bg-background px-3"><option value="">Select an employee</option>{employees.data?.data.map(employee => <option key={employee.id} value={employee.id}>{employee.employee_code} · {employee.first_name} {employee.last_name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Pay group<select required value={groupId} onChange={e => setGroupId(e.target.value)} className="h-9 rounded border bg-background px-3"><option value="">Select a group</option>{setup.groups.data?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Effective from<input required type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <label className="grid gap-1 text-sm">Effective through (optional)<input type="date" value={assignmentEndDate} onChange={e => setAssignmentEndDate(e.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <Button type="submit" disabled={!setup.groups.data?.length || setup.assignGroup.isPending} className="w-fit">Assign pay group</Button>
        </form>}
      </section>

      <section className="space-y-3 rounded-lg border p-4">
        <h2 className="text-lg font-semibold">Versioned payroll policies</h2>
        {setup.policies.data?.map(policy => <article key={policy.id} className="flex flex-wrap items-center justify-between gap-2 border-b py-2"><span>Version {policy.version} · effective {policy.effective_from} · {policy.confirmed ? 'confirmed' : 'draft'}</span>{canEdit && !policy.confirmed && <Button variant="outline" onClick={async () => { try { await setup.confirmPolicy.mutateAsync(policy.id); toast.success('Policy confirmed') } catch { toast.error('Policy is incomplete. Fill all required values and statutory source references before confirming.') } }} disabled={setup.confirmPolicy.isPending}>Confirm policy</Button>}</article>)}
        {canAdd && <form onSubmit={submitPolicy} className="space-y-3">
          <label className="grid gap-1 text-sm">Effective from<input required type="date" value={policyEffectiveDate} onChange={e => setPolicyEffectiveDate(e.target.value)} className="h-9 w-fit rounded border bg-background px-3" /></label>
          <label className="grid gap-1 text-sm">Policy data (JSON)<textarea required rows={16} value={policyJson} onChange={e => setPolicyJson(e.target.value)} className="w-full rounded border bg-background p-3 font-mono text-xs" /></label>
          <Button type="submit" disabled={setup.createPolicy.isPending}>Save policy draft</Button>
          <p className="text-xs text-muted-foreground">Confirmation records that the listed statutory source URLs were reviewed. Payroll finalization remains disabled until the attendance-driven calculation and independent review workflow is complete.</p>
        </form>}
      </section>
    </main>
  )
}
