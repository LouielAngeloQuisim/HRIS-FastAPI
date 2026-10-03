import { useState } from 'react'
import { usePhilHealthBrackets } from '@/lib/api/payroll-config'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { PhilHealthResourceForm } from './components/philhealth-resource-form'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'
import type { PhilHealthBracketPublic } from '@/lib/api/types'

export default function PhilHealthConfigPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('philhealth_config', 'view')
  const canCreate = useCan('philhealth_config', 'add')
  const canEdit = false // Current backend exposes list/create only.
  const canDelete = false // Current backend exposes list/create only.

  const { data, isPending, isError, refetch } = usePhilHealthBrackets((page - 1) * pageSize, pageSize)

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<PhilHealthBracketPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<PhilHealthBracketPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>You do not have permission to view PhilHealth config.</p>
      </div>
    )
  }

  return (
    <div className='space-y-4'>
      <p className='text-sm text-muted-foreground'>Existing brackets can be viewed and new brackets added. Editing and deletion are not yet available.</p>
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-bold'>PhilHealth Configuration</h1>
          <p className='text-muted-foreground'>{data?.count ?? 0} bracket records</p>
        </div>
        {canCreate && (
          <Button
            data-testid="add-philhealth-button"
            onClick={() => {
              setEditing(null)
              setOpen(true)
            }}
          >
            Add PhilHealth Bracket
          </Button>
        )}
      </div>
      {isPending && <p className='text-sm text-muted-foreground'>Loading...</p>}
      {isError && (
        <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
          <p className='text-sm text-muted-foreground'>Failed to load PhilHealth brackets.</p>
          <button type='button' onClick={() => refetch()} className='text-sm font-medium text-primary underline underline-offset-4' data-testid="retry-button">Try again</button>
        </div>
      )}
      {data && (
        <div className='overflow-x-auto rounded-lg border'>
          <table className='w-full text-sm'>
            <thead>
              <tr className='border-b bg-muted/50'>
                <th className='p-2 text-left'>Salary Min</th>
                <th className='p-2 text-left'>Salary Max</th>
                <th className='p-2 text-left'>Rate</th>
                <th className='p-2 text-left'>Employer Share</th>
                <th className='p-2 text-left'>Employee Share</th>
                <th className='p-2 text-left'>Effective Date</th>
                <th className='p-2 text-right'>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr key={item.id} className='border-b last:border-0 hover:bg-muted/50'>
                  <td className='p-2'>{Number(item.salary_min).toLocaleString()}</td>
                  <td className='p-2'>{Number(item.salary_max).toLocaleString()}</td>
                  <td className='p-2'>{item.rate}%</td>
                  <td className='p-2'>{item.employer_share}%</td>
                  <td className='p-2'>{item.employee_share}%</td>
                  <td className='p-2'>{item.effective_date}</td>
                  <td className='p-2 text-right'>
                    {canEdit && (
                      <Button
                        data-testid={`edit-philhealth-button-${item.id}`}
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
                        data-testid={`delete-philhealth-button-${item.id}`}
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
      <PhilHealthResourceForm
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
