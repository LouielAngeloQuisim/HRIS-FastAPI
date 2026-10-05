import { useState } from 'react'
import { useBIRBrackets } from '@/lib/api/payroll-config'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { BIRResourceForm } from './components/bir-resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'
import type { BIRBracketPublic } from '@/lib/api/types'

export default function BIRConfigPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('bir_config', 'view')
  const canCreate = useCan('bir_config', 'add')
  const canEdit = useCan('bir_config', 'edit')
  const canDelete = useCan('bir_config', 'delete')

  const { data, isPending, isError, refetch } = useBIRBrackets((page - 1) * pageSize, pageSize)

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<BIRBracketPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<BIRBracketPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>You do not have permission to view BIR config.</p>
      </div>
    )
  }

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-bold'>BIR Configuration</h1>
          <p className='text-muted-foreground'>{data?.count ?? 0} bracket records</p>
        </div>
        {canCreate && (
          <Button
            data-testid="add-bir-button"
            onClick={() => {
              setEditing(null)
              setOpen(true)
            }}
          >
            Add BIR Bracket
          </Button>
        )}
      </div>
      {isPending && <p className='text-sm text-muted-foreground'>Loading...</p>}
      {isError && (
        <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
          <p className='text-sm text-muted-foreground'>Failed to load BIR brackets.</p>
          <button type='button' onClick={() => refetch()} className='text-sm font-medium text-primary underline underline-offset-4' data-testid="retry-button">Try again</button>
        </div>
      )}
      {data && (
        <div className='overflow-x-auto rounded-lg border'>
          <table className='w-full text-sm'>
            <thead>
              <tr className='border-b bg-muted/50'>
                <th className='p-2 text-left'>Period</th>
                <th className='p-2 text-left'>Bracket Min</th>
                <th className='p-2 text-left'>Bracket Max</th>
                <th className='p-2 text-left'>Base Tax</th>
                <th className='p-2 text-left'>Excess Rate</th>
                <th className='p-2 text-left'>Effective Date</th>
                <th className='p-2 text-right'>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className='border-b last:border-0 hover:bg-muted/50'>
                  <td className='p-2'>{item.period}</td>
                  <td className='p-2'>{Number(item.bracket_min).toLocaleString()}</td>
                  <td className='p-2'>{item.bracket_max === null ? 'No upper limit' : Number(item.bracket_max).toLocaleString()}</td>
                  <td className='p-2'>{Number(item.base_tax).toLocaleString()}</td>
                  <td className='p-2'>{item.excess_rate}%</td>
                  <td className='p-2'>{item.effective_date}</td>
                  <td className='p-2 text-right'>
                    {canEdit && (
                      <Button
                        data-testid={`edit-bir-button-${item.id}`}
                        variant='ghost'
                        size='sm'
                        onClick={() => {
                          setEditing(item)
                          setOpen(true)
                        }}
                      >
                        Edit
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        data-testid={`delete-bir-button-${item.id}`}
                        variant='ghost'
                        size='sm'
                        onClick={() => {
                          setDeleteItem(item)
                          setDeleteOpen(true)
                        }}
                        className='text-destructive'
                      >
                        Delete
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <BIRResourceForm
        key={editing?.id ?? 'new'}
        item={editing}
        open={open}
        onClose={() => {
          setOpen(false)
          setEditing(null)
        }}
      />
      <ResourceDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        item={deleteItem}
        onClose={() => {
          setDeleteOpen(false)
          setDeleteItem(null)
        }}
      />
    </div>
  )
}
