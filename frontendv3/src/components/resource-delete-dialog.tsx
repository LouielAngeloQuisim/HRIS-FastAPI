import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ConfirmDialog } from '@/components/confirm-dialog'

type ResourceDeleteDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  entityName: string
  entityLabel: string
  onConfirm: () => void | Promise<void>
  isPending?: boolean
  conflictError?: { message: string } | null
}

export function ResourceDeleteDialog({
  open,
  onOpenChange,
  entityName,
  entityLabel,
  onConfirm,
  isPending = false,
  conflictError = null,
}: ResourceDeleteDialogProps) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      destructive
      isLoading={isPending}
      className="max-w-md"
      title={
        <span className="text-destructive">
          <AlertTriangle className="me-1 inline-block stroke-destructive" size={18} />{' '}
          Delete {entityName}
        </span>
      }
      desc={
        <div className="space-y-3">
          <p>
            Are you sure you want to delete{' '}
            <span className="font-bold">{entityLabel}</span>?
            <br />
            This action cannot be undone.
          </p>

          {conflictError && (
            <Alert variant="destructive">
              <AlertTitle>Cannot delete</AlertTitle>
              <AlertDescription>{conflictError.message}</AlertDescription>
            </Alert>
          )}
        </div>
      }
      confirmText="Delete"
      handleConfirm={onConfirm}
    />
  )
}
