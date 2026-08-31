import { getRouteApi } from '@tanstack/react-router'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { useCan } from '@/context/permissions-provider'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Upload } from 'lucide-react'
import { CsvImportWizard } from './components/csv-import/csv-import-wizard'
import { useEmployees } from '@/lib/api/employees'
import { EmployeesTable } from './components/employees-table'

const route = getRouteApi('/_authenticated/employees/')

export function Employees() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const canView = useCan('emp_list', 'view')

  const page = typeof search.page === 'number' ? search.page : 1
  const pageSize = typeof search.pageSize === 'number' ? search.pageSize : 10

  const { data, isPending, isError, refetch } = useEmployees(page, pageSize)
  const employees = (data?.data ?? []).map((e) => ({
    ...e,
    birthdate: e.birthdate ?? '',
  }))
  const count = data?.count ?? 0
  const [csvImportOpen, setCsvImportOpen] = useState(false)

  return (
    <EmployeesAuthGate canView={canView}>
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>

      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex items-center justify-between'>
            <div>
              <h2 className='text-2xl font-bold tracking-tight'>Employee List</h2>
              <p className='text-muted-foreground'>
                {count} employee{count === 1 ? '' : 's'} total
              </p>
            </div>
            <Button variant='outline' onClick={() => setCsvImportOpen(true)}>
              <Upload className='mr-2 h-4 w-4' /> Import CSV
            </Button>
          </div>
        {isPending && (
          <div className='text-sm text-muted-foreground'>Loading employees…</div>
        )}
        {isError && !isPending && (
          <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
            <p className='text-sm text-muted-foreground'>
              Failed to load employees.
            </p>
            <button
              type='button'
              onClick={() => refetch()}
              className='text-sm font-medium text-primary underline underline-offset-4'
            >
              Try again
            </button>
          </div>
        )}
        {!isPending && !isError && (
          <EmployeesTable
            data={employees}
            count={count}
            search={search as Record<string, unknown>}
            navigate={navigate}
          />
        )}
      </Main>
      <CsvImportWizard open={csvImportOpen} onOpenChange={setCsvImportOpen} />
    </EmployeesAuthGate>
  )
}

function EmployeesAuthGate({
  canView,
  children,
}: {
  canView: boolean
  children: React.ReactNode
}) {
  if (!canView) {
    return (
      <Main>
        <p className='text-sm text-muted-foreground'>
          You do not have permission to view employees.
        </p>
      </Main>
    )
  }
  return <>{children}</>
}