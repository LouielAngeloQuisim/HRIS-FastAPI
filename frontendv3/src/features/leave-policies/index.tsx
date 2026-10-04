import { useState } from 'react'
import { useLeavePolicies, useDeleteLeavePolicy } from '@/lib/api/leave-policies'
import type { LeavePolicyPublic } from '@/lib/api/types'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { ConfigDrawer } from '@/components/config-drawer'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { LeavePolicyForm } from './components/policy-form'
import { LeavePolicyDeleteDialog } from './components/policy-delete-dialog'

export default function LeavePoliciesPage() {
  const canView = useCan('leave_policy', 'view')
  const canAdd = useCan('leave_policy', 'add')
  const canEdit = useCan('leave_policy', 'edit')
  const canDelete = useCan('leave_policy', 'delete')

  const [page] = useState(1)
  const pageSize = 20
  const { data, isPending, isError, refetch } = useLeavePolicies(page, pageSize)
  const deleteMutation = useDeleteLeavePolicy()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<LeavePolicyPublic | null>(null)
  const [deleteItem, setDeleteItem] = useState<LeavePolicyPublic | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const handleAdd = () => {
    setEditing(null)
    setOpen(true)
  }

  const handleEdit = (policy: LeavePolicyPublic) => {
    setEditing(policy)
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
    setEditing(null)
  }

  const handleArchive = (policy: LeavePolicyPublic) => {
    setDeleteItem(policy)
    setDeleteOpen(true)
  }

  if (!canView) {
    return (
      <Main>
        <p className='text-muted-foreground'>You do not have permission to view leave policies.</p>
      </Main>
    )
  }

  return (
    <div className='space-y-4'>
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex items-center justify-between'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>Leave Policies</h2>
            <p className='text-muted-foreground'>{data?.count ?? 0} policy records</p>
          </div>
          {canAdd && (
            <Button data-testid='add-leave-policy-button' onClick={handleAdd}>
              Add Leave Policy
            </Button>
          )}
        </div>
        {isPending && <div className='text-sm text-muted-foreground'>Loading policies…</div>}
        {isError && !isPending && (
          <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
            <p className='text-sm text-muted-foreground'>Failed to load policies.</p>
            <button
              type='button'
              onClick={() => refetch()}
              className='text-sm font-medium text-primary underline underline-offset-4'
            >
              Try again
            </button>
          </div>
        )}
        {!isPending && !isError && data && (
          <div className='overflow-x-auto rounded-lg border'>
            <table className='w-full text-sm'>
              <thead>
                <tr className='border-b bg-muted/50'>
                  <th className='p-2 text-left'>Code</th>
                  <th className='p-2 text-left'>Name</th>
                  <th className='p-2 text-left'>Cadence</th>
                  <th className='p-2 text-left'>Entitlement (days)</th>
                  <th className='p-2 text-left'>Status</th>
                  <th className='p-2 text-right'>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.data.length === 0 ? (
                  <tr>
                    <td colSpan={6} className='p-4 text-center text-muted-foreground'>
                      No leave policies configured. Click &quot;Add Leave Policy&quot; to configure one.
                    </td>
                  </tr>
                ) : (
                  data.data.map((policy) => (
                    <tr key={policy.id} className='border-b hover:bg-muted/30'>
                      <td className='p-2'>{policy.code}</td>
                      <td className='p-2 font-medium'>{policy.name}</td>
                      <td className='p-2'>{policy.cadence ?? '—'}</td>
                      <td className='p-2'>{policy.annual_entitlement_days ?? '0.00'}</td>
                      <td className='p-2'>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            policy.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {policy.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className='p-2 text-right'>
                        {canEdit && (
                          <Button
                            variant='ghost'
                            size='sm'
                            data-testid={`edit-leave-policy-button-${policy.id}`}
                            onClick={() => handleEdit(policy)}
                          >
                            Edit
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant='ghost'
                            size='sm'
                            className='text-destructive hover:text-destructive'
                            data-testid={`archive-leave-policy-button-${policy.id}`}
                            onClick={() => handleArchive(policy)}
                          >
                            Archive
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </Main>
      <LeavePolicyForm open={open} onClose={handleClose} initialData={editing ?? undefined} />
      <LeavePolicyDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        policy={deleteItem}
        onConfirm={async () => {
          if (!deleteItem) return
          try {
            await deleteMutation.mutateAsync(deleteItem.id)
          } finally {
            setDeleteOpen(false)
            setDeleteItem(null)
          }
        }}
      />
    </div>
  )
}
