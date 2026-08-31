import { api } from '@/lib/api/client'
import type { EmployeeProjectsPublic } from '@/lib/api/types'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useEmployeeProjects } from '@/lib/api/employee-projects'
import { Button } from '@/components/ui/button'
import { ResourceForm } from './components/resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'

export default function EmployeeProjectsPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('employeeProjects', 'view')
  const canCreate = useCan('employeeProjects', 'add')
  const canEdit = useCan('employeeProjects', 'edit')
  const canDelete = useCan('employeeProjects', 'delete')

  const { data, isPending, isError, refetch } = useEmployeeProjects(page, pageSize)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<EmployeeProjectsPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<EmployeeProjectsPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view employeeProjects.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Employee Projects</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
        {canCreate && <Button onClick={() => { setEditing(null); setOpen(true) }}>Add EmployeeProjects</Button>}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load employeeProjects.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Employee</th>
                <th className="p-2 text-left">Project</th>
                <th className="p-2 text-left">Date</th>
                <th className="p-2 text-left">Rendered Hours</th>
                <th className="p-2 text-left">Task</th>
                <th className="p-2 text-left">Assigned</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-2">{item.employee_id ?? "—"}</td>
                  <td className="p-2">{item.project_id ?? "—"}</td>
                  <td className="p-2">{item.date ?? "—"}</td>
                  <td className="p-2">{item.rendered_hours ?? "—"}</td>
                  <td className="p-2">{item.task ?? "—"}</td>
                  <td className="p-2">{item.is_assigned ?? "—"}</td>
                  <td className="p-2 text-right">
                    {canEdit && <Button variant="ghost" size="sm" onClick={() => { setEditing(item); setOpen(true) }}>Edit</Button>}
                    {canDelete && <Button variant="ghost" size="sm" onClick={() => { setDeleteItem(item); setDeleteOpen(true) }} className="text-destructive">Delete</Button>}
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
        resourceType="Employee Project"
        deleteFn={(id: string) => api.delete('/employee-projects/' + id).then(r => r.data)}
        queryKey={['employee-projects']}
      />
    </div>
  )
}