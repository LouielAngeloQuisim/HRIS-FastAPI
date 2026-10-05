import { relationshipLabel, useRelationshipLabels } from '@/lib/api/relationship-labels'
import { api } from '@/lib/api/client'
import type { EmpTaskPublic } from '@/lib/api/types'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useEmpTasks } from '@/lib/api/emp-tasks'
import { Button } from '@/components/ui/button'
import { ResourceForm } from './components/resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'

export default function EmpTaskPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('empTasks', 'view')
  const canCreate = useCan('empTasks', 'add')
  const canEdit = useCan('empTasks', 'edit')
  const canDelete = useCan('empTasks', 'delete')

  const { data, isPending, isError, refetch } = useEmpTasks(page, pageSize)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<EmpTaskPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<EmpTaskPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const emp_project_idLabels = useRelationshipLabels('employee-projects', (data?.data ?? []).map(item => item.emp_project_id))

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view empTasks.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Emp Tasks</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
         {canCreate && <Button onClick={() => { setEditing(null); setOpen(true) }} data-testid="add-emp-task-button">Add EmpTask</Button>}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load empTasks.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Employee Project</th>
                <th className="p-2 text-left">Task Description</th>
                <th className="p-2 text-left">Rendered Hours</th>
                <th className="p-2 text-left">Assigned Hours</th>
                <th className="p-2 text-left">Date</th>
                <th className="p-2 text-left">Approved</th>
                <th className="p-2 text-left">Adjusted</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-2">{relationshipLabel(emp_project_idLabels.data, item.emp_project_id)}</td>
                  <td className="p-2">{item.task_desc ?? "—"}</td>
                  <td className="p-2">{item.rendered_hours ?? "—"}</td>
                  <td className="p-2">{item.assigned_hours ?? "—"}</td>
                  <td className="p-2">{item.date ?? "—"}</td>
                  <td className="p-2">{item.approved == null ? "Not set" : item.approved ? "Yes" : "No"}</td>
                  <td className="p-2">{item.is_adjusted == null ? "Not set" : item.is_adjusted ? "Yes" : "No"}</td>
                  <td className="p-2 text-right">
                     {canEdit && <Button variant="ghost" size="sm" onClick={() => { setEditing(item); setOpen(true) }} data-testid={`edit-emp-task-button-${item.id}`}>Edit</Button>}
                     {canDelete && <Button variant="ghost" size="sm" onClick={() => { setDeleteItem(item); setDeleteOpen(true) }} className="text-destructive" data-testid={`delete-emp-task-button-${item.id}`}>Delete</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ResourceForm key={(editing as { id?: string } | null)?.id ?? 'new'} item={editing} open={open} onClose={() => setOpen(false)} />
      <ResourceDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        item={deleteItem}
        onClose={() => setDeleteOpen(false)}
        resourceType="Emp Task"
        deleteFn={(id: string) => api.delete('/emp-tasks/' + id).then(r => r.data)}
        queryKey={['emp-tasks']}
      />
    </div>
  )
}