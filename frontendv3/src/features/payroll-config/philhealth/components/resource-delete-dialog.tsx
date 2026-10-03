import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useDeletePhilHealthBracket } from '@/lib/api/payroll-config'
import type { PhilHealthBracketPublic } from '@/lib/api/types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  item: PhilHealthBracketPublic | null
  onClose: () => void
}

export function ResourceDeleteDialog({ open, onOpenChange, item, onClose }: Props) {
  const deleteMutation = useDeletePhilHealthBracket()

  const handleDelete = async () => {
    if (!item) return
    try {
      await deleteMutation.mutateAsync(item.id)
      onClose()
    } catch {
      // error handled by mutation
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete PhilHealth Bracket</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this PhilHealth bracket? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant='outline'>Cancel</Button>
          </DialogClose>
          <Button
            variant='destructive'
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
