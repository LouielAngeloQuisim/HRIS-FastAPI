import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { toast } from 'sonner'
import { useDashboard } from './data/dashboard'
import { DashboardTiles, DashboardTilesSkeleton } from './components/dashboard-tiles'

export function Dashboard() {
  const { data, isPending, isError, refetch } = useDashboard()

  if (isError) {
    toast.error('Failed to load dashboard metrics.')
  }

  return (
    <>
      <Header>
        <Search />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>

      <Main>
        <div className='mb-2 flex items-center justify-between space-y-2'>
          <h1 className='text-2xl font-bold tracking-tight'>Dashboard</h1>
        </div>

        {isPending ? (
          <DashboardTilesSkeleton />
        ) : data ? (
          <DashboardTiles data={data} />
        ) : (
          <button
            type='button'
            className='text-sm text-muted-foreground underline'
            onClick={() => refetch()}
          >
            No data. Retry.
          </button>
        )}
      </Main>
    </>
  )
}
