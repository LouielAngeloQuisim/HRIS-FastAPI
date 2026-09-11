import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useHolidayConfigs } from '@/lib/api/holidays'
import { Button } from '@/components/ui/button'
import { ResourceForm } from './components/resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'
import type { HolidayConfigPublic } from '@/lib/api/types'
import { api } from '@/lib/api/client'

export default function HolidaysPage() {
  const [page] = useState(1)
  const pageSize = 50
  const canView = useCan('holiday_config', 'view')
  const canAdd = useCan('holiday_config', 'add')
  const canEdit = useCan('holiday_config', 'edit')
  const canDelete = useCan('holiday_config', 'delete')

  const { data, isPending, isError, refetch } = useHolidayConfigs(page, pageSize)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<HolidayConfigPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<HolidayConfigPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view holiday configurations.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Holiday Configuration</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} holiday configs</p>
        </div>
        {canAdd && (
          <Button onClick={() => { setEditing(null); setFormOpen(true) }} data-testid="holiday-add-button">
            Add Holiday
          </Button>
        )}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load holiday configurations.</p>
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
                <th className="p-2 text-left">Month/Day</th>
                <th className="p-2 text-left">Type</th>
                <th className="p-2 text-left">Region</th>
                <th className="p-2 text-center">Recurring</th>
                <th className="p-2 text-center">Active</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.length === 0 ? (
                <tr><td colSpan={8} className="p-4 text-center text-muted-foreground">No holiday configs found.</td></tr>
              ) : (
                data.data.map((item) => (
                  <tr key={item.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="p-2">{item.code ?? '—'}</td>
                    <td className="p-2">{item.name ?? '—'}</td>
                    <td className="p-2">{item.month_day ?? '—'}</td>
                    <td className="p-2">{item.type ?? '—'}</td>
                    <td className="p-2">{item.region_code ?? '—'}</td>
                    <td className="p-2 text-center">{item.is_recurring ? 'Yes' : 'No'}</td>
                    <td className="p-2 text-center">{item.is_active ? 'Yes' : 'No'}</td>
                     <td className="p-2 text-right">
                       {canEdit && <Button variant="ghost" size="sm" onClick={() => { setEditing(item); setFormOpen(true) }} data-testid={`edit-holiday-button-${item.id}`}>Edit</Button>}
                       {canDelete && <Button variant="ghost" size="sm" onClick={() => { setDeleteItem(item); setDeleteOpen(true) }} className="text-destructive" data-testid={`delete-holiday-button-${item.id}`}>Delete</Button>}
                     </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
      <ResourceForm
        key={(editing as { id?: string } | null)?.id ?? 'new'}
        item={editing}
        open={formOpen}
        onClose={() => setFormOpen(false)}
      />
      <ResourceDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        item={deleteItem}
        onClose={() => setDeleteOpen(false)}
        resourceType="Holiday Configuration"
        deleteFn={(id: string) => api.delete('/holidays/' + id).then(r => r.data)}
        queryKey={['holiday-configs']}
      />
    </div>
  )
}
