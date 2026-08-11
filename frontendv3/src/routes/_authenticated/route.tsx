import { createFileRoute, redirect } from '@tanstack/react-router'
import { AuthenticatedLayout } from '@/components/layout/authenticated-layout'
import { getAccessToken, getRefreshToken } from '@/lib/api/client'

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: ({ location }) => {
    const hasSession = Boolean(getAccessToken() && getRefreshToken())
    if (!hasSession) {
      throw redirect({
        to: '/sign-in',
        search: { redirect: location.href },
      })
    }
  },
  component: AuthenticatedLayout,
})
