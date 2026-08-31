import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useRoles } from '@/lib/api/roles'
import { Button } from '@/components/ui/button'
import { RoleForm } from './components/role-form'
import { PermissionMatrix } from './components/permission-matrix'

export default function RolesPage() {
  const [page] = useState(1)
  const pageSize = 20
  const canView = useCan('administration', 'view')
  const canCreate = useCan('administration', 'add')
  const canUpdate = useCan('administration', 'edit')

  const { data, isPending, isError, refetch } = useRoles(page, pageSize)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [matrixRoleId, setMatrixRoleId] = useState<string | null>(null)
  const [matrixRoleName, setMatrixRoleName] = useState<string>('')

  const editingRole = editingId ? data?.data.find(r => r.id === editingId) ?? null : null

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view roles.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Roles</h1>
          <p className="text-muted-foreground">{data?.count ?? 0} roles</p>
        </div>
        {canCreate && (
          <Button onClick={() => { setEditingId(null); setFormOpen(true) }}>Add Role</Button>
        )}
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load roles.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Name</th>
                <th className="p-2 text-left">Code</th>
                <th className="p-2 text-left">Permissions</th>
                <th className="p-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((role) => (
                <tr key={role.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="p-2">{role.name}</td>
                  <td className="p-2">{role.code ?? '—'}</td>
                  <td className="p-2">{0} permissions</td>
                  <td className="p-2 text-right">
                    <Button variant="ghost" size="sm" onClick={() => { setMatrixRoleId(role.id); setMatrixRoleName(role.name) }}>Permissions</Button>
                    {canUpdate && (
                      <Button variant="ghost" size="sm" onClick={() => { setEditingId(role.id); setFormOpen(true) }}>Edit</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <RoleForm
        open={formOpen}
        role={editingRole}
        onClose={() => setFormOpen(false)}
      />
      <PermissionMatrix
        key={matrixRoleId}
        open={Boolean(matrixRoleId)}
        roleId={matrixRoleId}
        roleName={matrixRoleName}
        onClose={() => setMatrixRoleId(null)}
      />
    </div>
  )
}
