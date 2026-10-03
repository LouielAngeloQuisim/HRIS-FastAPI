import { redirect } from '@tanstack/react-router'
import { fetchMe } from '@/lib/api/auth'
import { useAuthStore } from '@/stores/auth-store'

/** Authorize direct navigation even before the layout hydrates the user. */
export async function assertSuperAdmin() {
  const user = useAuthStore.getState().auth.user
  let isSuperuser = user?.isSuperuser ?? false
  if (!user) {
    try {
      isSuperuser = (await fetchMe()).is_superuser
    } catch {
      isSuperuser = false
    }
  }
  if (!isSuperuser) throw redirect({ to: '/' })
}
