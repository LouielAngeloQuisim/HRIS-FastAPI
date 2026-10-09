import { useState } from 'react'
import { useSSSBrackets } from '@/lib/api/payroll-config'
import type { SSSBracketPublic } from '@/lib/api/types'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { ResourceDeleteDialog } from './components/resource-delete-dialog'
import { SSSResourceForm } from './components/sss-resource-form'

export default function SSSConfigPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('sss_config', 'view')
  const canCreate = useCan('sss_config', 'add')
  const canEdit = useCan('sss_config', 'edit')
  const canDelete = useCan('sss_config', 'delete')

  const { data, isPending, isError, refetch } = useSSSBrackets(
    (page - 1) * pageSize,
    pageSize
  )

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<SSSBracketPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<SSSBracketPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>
          You do not have permission to view SSS config.
        </p>
      </div>
    )
  }

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-bold'>SSS Configuration</h1>
          <p className='text-muted-foreground'>
            {data?.count ?? 0} bracket records
          </p>
        </div>
        {canCreate && (
          <Button
            data-testid='add-sss-button'
            onClick={() => {
              setEditing(null)
              setOpen(true)
            }}
          >
            Add SSS Bracket
          </Button>
        )}
      </div>
      {isPending && <p className='text-sm text-muted-foreground'>Loading...</p>}
      {isError && (
        <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
          <p className='text-sm text-muted-foreground'>
            Failed to load SSS brackets.
          </p>
          <button
            type='button'
            onClick={() => refetch()}
            className='text-sm font-medium text-primary underline underline-offset-4'
            data-testid='retry-button'
          >
            Try again
          </button>
        </div>
      )}
      {data && (
        <div className='overflow-x-auto rounded-lg border'>
          <table className='w-full text-sm'>
            <thead>
              <tr className='border-b bg-muted/50'>
                <th className='p-2 text-left'>Compensation Min</th>
                <th className='p-2 text-left'>Compensation Max</th>
                <th className='p-2 text-left'>Mapped MSC</th>
                <th className='p-2 text-left'>Employer SS</th>
                <th className='p-2 text-left'>Employer EC</th>
                <th className='p-2 text-left'>Employer MPF</th>
                <th className='p-2 text-left'>Employee SS</th>
                <th className='p-2 text-left'>Employee MPF</th>
                <th className='p-2 text-left'>Effective Date</th>
                <th className='p-2 text-right'>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((item) => (
                <tr
                  key={item.id}
                  className='border-b last:border-0 hover:bg-muted/50'
                >
                  <td className='p-2'>
                    {item.compensation_min === null
                      ? '—'
                      : Number(item.compensation_min).toLocaleString()}
                  </td>
                  <td className='p-2'>
                    {item.compensation_max === null
                      ? 'No upper limit'
                      : Number(item.compensation_max).toLocaleString()}
                  </td>
                  <td className='p-2'>
                    {item.monthly_salary_credit === null
                      ? 'Not configured'
                      : `₱${Number(item.monthly_salary_credit).toLocaleString()}`}
                  </td>
                  <td className='p-2'>
                    ₱
                    {Number(item.employer_ss).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className='p-2'>
                    ₱{Number(item.employer_ec).toLocaleString()}
                  </td>
                  <td className='p-2'>
                    ₱
                    {Number(item.employer_mpf).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className='p-2'>
                    ₱
                    {Number(item.employee_ss).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className='p-2'>
                    ₱
                    {Number(item.employee_mpf).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className='p-2'>{item.effective_date}</td>
                  <td className='p-2 text-right'>
                    {canEdit && (
                      <Button
                        data-testid={`edit-sss-button-${item.id}`}
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
                        data-testid={`delete-sss-button-${item.id}`}
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
      <SSSResourceForm
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
