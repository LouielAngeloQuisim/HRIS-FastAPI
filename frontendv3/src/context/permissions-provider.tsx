import { createContext, useContext, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api/client'
import { type MyPermissions, type PermissionAction } from '@/lib/api/types'

const PERMISSIONS_KEY = ['permissions'] as const
const REFRESH_INTERVAL_MS = 5 * 60 * 1000 // 5 minutes

async function fetchPermissions(): Promise<MyPermissions> {
  const { data } = await api.get<MyPermissions>('/rbac/me/permissions')
  return data
}

const PermissionsContext = createContext<MyPermissions | null | undefined>(
  undefined
)

interface PermissionsProviderProps {
  enabled: boolean
  children: ReactNode
}

/**
 * Mounted once for the authenticated session (in AuthenticatedLayout), not per
 * page, so the 5-minute refetch interval keeps running regardless of route.
 * Q5: refetch on interval + on login; never on every navigation.
 */
export function PermissionsProvider({
  enabled,
  children,
}: PermissionsProviderProps) {
  const query = useQuery({
    queryKey: PERMISSIONS_KEY,
    queryFn: fetchPermissions,
    enabled,
    staleTime: REFRESH_INTERVAL_MS,
    refetchInterval: REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: true,
  })

  return (
    <PermissionsContext value={enabled ? (query.data ?? null) : null}>
      {children}
    </PermissionsContext>
  )
}

function usePermissions(): MyPermissions | null {
  const ctx = useContext(PermissionsContext)
  if (ctx === undefined) {
    throw new Error('usePermissions must be used within a PermissionsProvider')
  }
  return ctx
}

/**
 * Reactive permission check. Reads the live permissions map (kept fresh by the
 * provider's background refetch). Superusers bypass all checks. Deny-by-default:
 * a missing module/action entry means no access.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useCan(
  module: string,
  action: PermissionAction = 'view'
): boolean {
  const permissions = usePermissions()
  if (permissions?.is_superuser) return true
  const modulePerms = permissions?.permissions[module]
  if (!modulePerms) return false
  return modulePerms[action] === true
}

// eslint-disable-next-line react-refresh/only-export-components
export function useRoleCode(): string | null {
  return usePermissions()?.role_code ?? null
}
