import { api } from '@/lib/api/client'
import type { SubdivisionPublic } from '@/lib/api/types'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useSubdivisions } from '@/lib/api/subdivisions'
import { Button } from '@/components/ui/button'
import { ResourceForm } from './components/resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'
import { useNavigate } from '@tanstack/react-router'

export default function SubdivisionPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('subdivision', 'view')
  const canCreate = useCan('subdivision', 'add')
  const canEdit = useCan('subdivision', 'edit')
  const canDelete = useCan('subdivision', 'delete')
  const navigate = useNavigate()

  const { data, isPending, isError, refetch } = useSubdivisions(page, pageSize)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<SubdivisionPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<SubdivisionPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view subdivisions.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Subdivisions</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
        <div className="flex gap-2">
          {canCreate && (
            <>
              <Button variant="default" onClick={() => navigate({ to: '/subdivisions/wizard' })}>
                Launch Wizard
              </Button>
              <Button onClick={() => { setEditing(null); setOpen(true) }}>Add Subdivision</Button>
            </>
          )}
        </div>
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load subdivisions.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Subdivision Code</th>
                <th className="p-2 text-left">Name</th>
                <th className="p-2 text-left">Description</th>
                <th className="p-2 text-left">Location</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-2">{item.subdivision_code ?? "—"}</td>
                  <td className="p-2">{item.name ?? "—"}</td>
                  <td className="p-2">{item.description ?? "—"}</td>
                  <td className="p-2">{item.location ?? "—"}</td>
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
        resourceType="Subdivision"
        deleteFn={(id: string) => api.delete('/subdivisions/' + id).then(r => r.data)}
        queryKey={['subdivisions']}
      />
    </div>
  )
}