import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useCan } from '@/context/permissions-provider'
import { toast } from 'sonner'
import { Save } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useRolePermissions } from '@/lib/api/roles'

const PERMISSION_MODULES = [
  'division',
  'department',
  'subdivision',
  'position',
  'project_type',
  'projects',
  'phase',
  'blocks',
  'lots',
  'category',
  'models',
  'model_types',
  'owner',
  'emp_project',
  'emp_task',
  'emp_list',
  'emp_settings',
  'administration',
]

const ACTIONS = ['view', 'add', 'edit', 'delete'] as const

type PermissionMatrixProps = {
  open: boolean
  roleId: string | null
  roleName: string
  onClose: () => void
}

export function PermissionMatrix({ open, roleId, roleName, onClose }: PermissionMatrixProps) {
  const qc = useQueryClient()
  const canEdit = useCan('administration', 'edit')
  const { data: loadedPermissions } = useRolePermissions(roleId)
  const [draftPermissions, setDraftPermissions] = useState<string[] | null>(null)

  const permissions = draftPermissions ?? loadedPermissions ?? []

  const updateMutation = useMutation({
    mutationFn: async (newPermissions: string[]) => {
      const { data } = await api.patch(`/rbac/roles/${roleId}`, {
        permissions: newPermissions,
      })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roles'] })
      toast.success(`Permissions updated for ${roleName}`)
      onClose()
    },
    onError: () => {
      toast.error('Failed to update permissions')
    },
  })

  const togglePermission = useCallback((permission: string) => {
    setDraftPermissions(prev => {
      const base = prev ?? loadedPermissions ?? []
      if (base.includes(permission)) {
        return base.filter(p => p !== permission)
      }
      return [...base, permission]
    })
  }, [loadedPermissions])

  const handleSave = () => {
    updateMutation.mutate(permissions)
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="flex flex-col max-w-2xl max-h-[90vh]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Permissions for {roleName}</DialogTitle>
          <DialogDescription>
            Toggle permissions to control what this role can access.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto pr-2 space-y-4">
          {PERMISSION_MODULES.map(module => (
            <div key={module}>
              <h4 className="mb-2 text-sm font-medium capitalize">{module.replace(/_/g, ' ')}</h4>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {ACTIONS.map(action => {
                  const permission = `${module}.${action}`
                  const isChecked = permissions.includes(permission)
                  return (
                    <div key={permission} className="flex items-center space-x-2">
                      <Checkbox
                        id={permission}
                        checked={isChecked}
                        onCheckedChange={() => togglePermission(permission)}
                        disabled={!canEdit}
                      />
                      <Label htmlFor={permission} className="text-sm capitalize">
                        {action}
                      </Label>
                    </div>
                  )
                })}
              </div>
              <Separator className="mt-4" />
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
          {canEdit && (
            <Button onClick={handleSave} disabled={updateMutation.isPending}>
              <Save className="mr-2 h-4 w-4" />
              {updateMutation.isPending ? 'Saving...' : 'Save Permissions'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
