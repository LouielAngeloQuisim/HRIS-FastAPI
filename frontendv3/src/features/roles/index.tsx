import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useRoles } from '@/lib/api/roles'
import { Button } from '@/components/ui/button'
import { RoleForm } from './components/role-form'
import { PermissionMatrix } from './components/permission-matrix'

export default function RolesPage() {
  const [page, setPage] = useState(1)
  const pageSize = 20
  const canView = useCan('administration', 'view')
  const canCreate = useCan('administration', 'add')
  const canUpdate = useCan('administration', 'edit')

  const { data, isPending, isError, refetch } = useRoles(page, pageSize)
  const totalPages = data ? Math.max(1, Math.ceil(data.count / pageSize)) : 1
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
           <Button onClick={() => { setEditingId(null); setFormOpen(true) }} data-testid="add-role-button">Add Role</Button>
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
                  <td className="p-2">
                    {role.name}
                    {role.is_system && <span className="ml-2 text-xs text-muted-foreground">(system)</span>}
                  </td>
                  <td className="p-2">{role.code ?? '—'}</td>
                  <td className="p-2">{0} permissions</td>
                  <td className="p-2 text-right">
                     {canUpdate && !role.is_system && (
                       <Button variant="ghost" size="sm" onClick={() => { setMatrixRoleId(role.id); setMatrixRoleName(role.name) }} data-testid={`role-permission-matrix-button-${role.id}`}>Permissions</Button>
                     )}
                     {canUpdate && !role.is_system && (
                       <Button variant="ghost" size="sm" onClick={() => { setEditingId(role.id); setFormOpen(true) }} data-testid={`edit-role-button-${role.id}`}>Edit</Button>
                     )}
                    {role.is_system && canUpdate && (
                      <Button variant="ghost" size="sm" disabled title="System roles cannot be edited">Edit (system)</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1 || isPending}
            onClick={() => setPage(p => p - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages || isPending}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </Button>
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
