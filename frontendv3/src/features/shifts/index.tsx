import { api } from '@/lib/api/client'
import type { ShiftsPublic } from '@/lib/api/types'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useShifts } from '@/lib/api/shifts'
import { Button } from '@/components/ui/button'
import { ResourceForm } from './components/resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'
import { useEmployees } from '@/lib/api/employees'
import { useCloseEmployeeShiftAssignment, useCreateEmployeeShiftAssignment, useEmployeeShiftAssignments } from '@/lib/api/shifts'
import { toast } from 'sonner'

export default function ShiftsPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('shifts', 'view')
  const canCreate = useCan('shifts', 'add')
  const canEdit = useCan('shifts', 'edit')
  const canDelete = useCan('shifts', 'delete')

  const { data, isPending, isError, refetch } = useShifts(page, pageSize)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<ShiftsPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<ShiftsPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [employeeId, setEmployeeId] = useState('')
  const [shiftId, setShiftId] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [effectiveTo, setEffectiveTo] = useState('')
  const [closeDates, setCloseDates] = useState<Record<string, string>>({})
  const employees = useEmployees(1, 500)
  const assignments = useEmployeeShiftAssignments()
  const createAssignment = useCreateEmployeeShiftAssignment()
  const closeAssignment = useCloseEmployeeShiftAssignment()

  const handleAssignmentCreate = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      await createAssignment.mutateAsync({ employee_id: employeeId, shift_id: shiftId, effective_from: effectiveFrom, effective_to: effectiveTo || null })
      setEmployeeId(''); setShiftId(''); setEffectiveFrom(''); setEffectiveTo('')
      toast.success('Shift assignment saved')
    } catch { toast.error('Could not save assignment. Check the employee, shift and effective dates for overlaps.') }
  }

  const handleAssignmentClose = async (id: string) => {
    const date = closeDates[id]
    if (!date) { toast.error('Choose the last effective work date.'); return }
    try { await closeAssignment.mutateAsync({ id, effective_to: date }); toast.success('Shift assignment closed') }
    catch { toast.error('Could not close this assignment. The end date may overlap a later assignment.') }
  }

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view shifts.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Shifts</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
         {canCreate && <Button onClick={() => { setEditing(null); setOpen(true) }} data-testid="add-shift-button">Add Shifts</Button>}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load shifts.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Code</th>
                <th className="p-2 text-left">Name</th>
                <th className="p-2 text-left">Start Time</th>
                <th className="p-2 text-left">End Time</th>
                <th className="p-2 text-left">Description</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-2">{item.code ?? "—"}</td>
                  <td className="p-2">{item.name ?? "—"}</td>
                  <td className="p-2">{item.start_time ?? "—"}</td>
                  <td className="p-2">{item.end_time ?? "—"}</td>
                  <td className="p-2">{item.description ?? "—"}</td>
                  <td className="p-2 text-right">
                     {canEdit && <Button variant="ghost" size="sm" onClick={() => { setEditing(item); setOpen(true) }} data-testid={`edit-shift-button-${item.id}`}>Edit</Button>}
                     {canDelete && <Button variant="ghost" size="sm" onClick={() => { setDeleteItem(item); setDeleteOpen(true) }} className="text-destructive" data-testid={`delete-shift-button-${item.id}`}>Delete</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <section className="space-y-3 rounded-lg border p-4" aria-label="Employee shift assignments">
        <div><h2 className="text-lg font-semibold">Employee shift assignments</h2><p className="text-sm text-muted-foreground">Attendance requires a shift effective on the work date. Assignments are date-based and cannot overlap.</p></div>
        {assignments.isError && <p role="alert" className="text-sm text-destructive">Shift assignments could not be loaded.</p>}
        {assignments.data?.data.map(assignment => {
          const employee = employees.data?.data.find(item => item.id === assignment.employee_id)
          const assignedShift = data?.data.find(item => item.id === assignment.shift_id)
          return <div key={assignment.id} className="flex flex-wrap items-end justify-between gap-3 border-b py-2 text-sm">
            <span>{employee ? `${employee.employee_code} · ${employee.first_name} ${employee.last_name}` : assignment.employee_id} · {assignedShift?.name ?? assignment.shift_id} · {assignment.effective_from}{assignment.effective_to ? ` to ${assignment.effective_to}` : ' onward'}</span>
            {!assignment.effective_to && canEdit && <div className="flex items-end gap-2"><label className="grid gap-1 text-xs">Last effective date<input type="date" value={closeDates[assignment.id] ?? ''} onChange={event => setCloseDates(current => ({ ...current, [assignment.id]: event.target.value }))} className="h-9 rounded border bg-background px-2" /></label><Button type="button" size="sm" variant="outline" disabled={closeAssignment.isPending} onClick={() => handleAssignmentClose(assignment.id)}>Close</Button></div>}
          </div>
        })}
        {!assignments.isPending && !assignments.data?.data.length && <p className="text-sm text-muted-foreground">No employee shifts assigned yet.</p>}
        {canCreate && <form onSubmit={handleAssignmentCreate} className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <label className="grid gap-1 text-sm">Employee<select required value={employeeId} onChange={event => setEmployeeId(event.target.value)} className="h-9 rounded border bg-background px-3"><option value="">Select employee</option>{employees.data?.data.map(employee => <option key={employee.id} value={employee.id}>{employee.employee_code} · {employee.first_name} {employee.last_name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Shift<select required value={shiftId} onChange={event => setShiftId(event.target.value)} className="h-9 rounded border bg-background px-3"><option value="">Select shift</option>{data?.data.map(shift => <option key={shift.id} value={shift.id}>{shift.name} ({shift.code})</option>)}</select></label>
          <label className="grid gap-1 text-sm">Effective from<input required type="date" value={effectiveFrom} onChange={event => setEffectiveFrom(event.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <label className="grid gap-1 text-sm">Effective through (optional)<input type="date" value={effectiveTo} onChange={event => setEffectiveTo(event.target.value)} className="h-9 rounded border bg-background px-3" /></label>
          <Button type="submit" disabled={!data?.data.length || !employees.data?.data.length || createAssignment.isPending} className="w-fit">Assign shift</Button>
        </form>}
      </section>
      <ResourceForm key={(editing as { id?: string } | null)?.id ?? 'new'} item={editing} open={open} onClose={() => setOpen(false)} />
      <ResourceDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        item={deleteItem}
        onClose={() => setDeleteOpen(false)}
        resourceType="Shift"
        deleteFn={(id: string) => api.delete('/shifts/' + id).then(r => r.data)}
        queryKey={['shifts']}
      />
    </div>
  )
}
