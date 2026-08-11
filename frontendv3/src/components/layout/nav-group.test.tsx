import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { LayoutDashboard, Users } from 'lucide-react'
import { NavGroup } from './nav-group'
import { PermissionsProvider } from '@/context/permissions-provider'
import { SidebarProvider } from '@/components/ui/sidebar'
import { type MyPermissions } from '@/lib/api/types'

const mockUseQuery = vi.hoisted(() => vi.fn())

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}))

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useLocation: () => '/',
    Link: ({
      children,
      to,
      className,
    }: {
      children?: React.ReactNode
      to: string
      className?: string
    }) => (
      <a href={to} className={className}>
        {children}
      </a>
    ),
  }
})

// Dashboard is ungated (no permission) -> always renders.
// Employees is gated on emp_list -> renders only when that permission exists.
const items = [
  { title: 'Dashboard', url: '/', icon: LayoutDashboard },
  {
    title: 'Employees',
    url: '/employees',
    icon: Users,
    permission: { module: 'emp_list' },
  },
] as const

function renderGroup(perms: MyPermissions | null) {
  mockUseQuery.mockReturnValue({ data: perms })
  return render(
    <PermissionsProvider enabled={true}>
      <SidebarProvider>
        <NavGroup title='Test' items={items as never} />
      </SidebarProvider>
    </PermissionsProvider>
  )
}

function renderedText(screen: { container: HTMLElement }): string {
  return screen.container.textContent ?? ''
}

describe('NavGroup permission filtering (render-level)', () => {
  it('hides the gated item and keeps the ungated item when permission is absent', async () => {
    const perms: MyPermissions = {
      role_code: 'SUR',
      is_superuser: false,
      permissions: {}, // emp_list absent
    }

    const screen = await renderGroup(perms)
    const text = renderedText(screen)

    // Ungated item still renders.
    expect(text).toContain('Dashboard')
    // Gated item is genuinely absent from the rendered DOM.
    expect(text).not.toContain('Employees')
  })

  it('renders the gated item when the user has that permission', async () => {
    const perms: MyPermissions = {
      role_code: 'SUR',
      is_superuser: false,
      permissions: {
        emp_list: { view: true, add: false, edit: false, delete: false },
      },
    }

    const screen = await renderGroup(perms)
    const text = renderedText(screen)

    expect(text).toContain('Dashboard')
    expect(text).toContain('Employees')
  })

  it('renders all items for a superuser', async () => {
    const perms: MyPermissions = {
      role_code: 'SADM',
      is_superuser: true,
      permissions: {},
    }

    const screen = await renderGroup(perms)
    const text = renderedText(screen)

    expect(text).toContain('Dashboard')
    expect(text).toContain('Employees')
  })
})
