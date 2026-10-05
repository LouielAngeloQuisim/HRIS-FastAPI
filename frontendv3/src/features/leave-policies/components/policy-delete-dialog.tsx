import { ResourceDeleteDialog } from '@/components/resource-delete-dialog'
import type { LeavePolicyPublic } from '@/lib/api/types'

type LeavePolicyDeleteDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  policy: LeavePolicyPublic | null
  onConfirm: () => void | Promise<void>
  isPending?: boolean
}

export function LeavePolicyDeleteDialog({
  open,
  onOpenChange,
  policy,
  onConfirm,
  isPending = false,
}: LeavePolicyDeleteDialogProps) {
  if (!policy) return null
  return (
    <ResourceDeleteDialog
      open={open}
      onOpenChange={onOpenChange}
      entityName='Leave Policy'
      entityLabel={policy.name}
      onConfirm={onConfirm}
      isPending={isPending}
    />
  )
}
