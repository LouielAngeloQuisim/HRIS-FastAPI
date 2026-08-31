import { api } from '@/lib/api/client'
import type { OwnerPublic } from '@/lib/api/types'
import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useOwners } from '@/lib/api/owners'
import { Button } from '@/components/ui/button'
import { ResourceForm } from './components/resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'

export default function OwnerPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('owners', 'view')
  const canCreate = useCan('owners', 'add')
  const canEdit = useCan('owners', 'edit')
  const canDelete = useCan('owners', 'delete')

  const { data, isPending, isError, refetch } = useOwners(page, pageSize)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<OwnerPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<OwnerPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view owners.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Owners</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} records</p>
        </div>
        {canCreate && <Button onClick={() => { setEditing(null); setOpen(true) }}>Add Owner</Button>}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load owners.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">First Name</th>
                <th className="p-2 text-left">Last Name</th>
                <th className="p-2 text-left">Lot No</th>
                <th className="p-2 text-left">Block</th>
                <th className="p-2 text-left">Email</th>
                <th className="p-2 text-left">Contact No</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-2">{item.first_name ?? "—"}</td>
                  <td className="p-2">{item.last_name ?? "—"}</td>
                  <td className="p-2">{item.lot_no ?? "—"}</td>
                  <td className="p-2">{item.block ?? "—"}</td>
                  <td className="p-2">{item.email ?? "—"}</td>
                  <td className="p-2">{item.contact_no ?? "—"}</td>
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
        resourceType="Owner"
        deleteFn={(id: string) => api.delete('/owners/' + id).then(r => r.data)}
        queryKey={['owners']}
      />
    </div>
  )
}