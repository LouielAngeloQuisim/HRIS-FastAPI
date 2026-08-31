import { useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { toast } from 'sonner'
import { extractDeleteErrorMessage } from '@/features/shared/components/resource-delete-dialog'

type ResourceDeleteDialogProps<T> = {
  open: boolean
  onOpenChange: (open: boolean) => void
  item: T | null
  onClose: () => void
  resourceType: string
  deleteFn: (id: string) => Promise<unknown>
  queryKey: string[]
}

export function ResourceDeleteDialog<T extends { id: string; name?: string }>({
  open,
  onOpenChange,
  item,
  onClose,
  resourceType,
  deleteFn,
  queryKey,
}: ResourceDeleteDialogProps<T>) {
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: (id: string) => deleteFn(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey })
      toast.success(`${resourceType} deleted successfully`)
      onClose()
    },
    onError: (err: unknown) => {
      toast.error(extractDeleteErrorMessage(err, resourceType))
    },
  })

  const title = useMemo(() => `Delete ${resourceType}`, [resourceType])
  const desc = useMemo(
    () => (
      <div>
        <p>Are you sure you want to delete this {resourceType.toLowerCase()}?</p>
        {item?.name && (
          <p className="mt-1 font-medium">
            &quot;{item.name}&quot; will be permanently removed.
          </p>
        )}
        <p className="mt-2 text-xs text-muted-foreground">This action cannot be undone.</p>
      </div>
    ),
    [item, resourceType]
  )

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      desc={desc}
      handleConfirm={() => item && mutation.mutate(item.id)}
      confirmText="Delete"
      destructive
      isLoading={mutation.isPending}
    />
  )
}
