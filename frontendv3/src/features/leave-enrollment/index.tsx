import { useState } from 'react'
import { useLeaveEnrollments, useLeavePolicies } from '@/lib/api/leave-policies'
import { useEmployees } from '@/lib/api/employees'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { ConfigDrawer } from '@/components/config-drawer'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { EnrollmentDialog } from './components/enrollment-dialog'

export default function LeaveEnrollmentsPage() {
  const canView = useCan('emp_leaves', 'view')
  const canAdd = useCan('emp_leaves', 'add')

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | undefined>(undefined)
  const [selectedYear, setSelectedYear] = useState<number>(2026)
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: employeesData, isPending: employeesPending } = useEmployees(1, 500)
  const employees = employeesData?.data ?? []

  const { data: enrollmentsData, isPending: _enrollmentsPending, isError, refetch } = useLeaveEnrollments(
    selectedEmployeeId,
    selectedYear
  )
  const enrollments = enrollmentsData?.data ?? []

  const { data: policiesData, isPending: policiesPending } = useLeavePolicies(1, 500)
  const policies = policiesData?.data ?? []

  const selectedEmployee = employees.find((e) => e.id === selectedEmployeeId)

  if (!canView) {
    return (
      <Main>
        <p className='text-muted-foreground'>You do not have permission to view leave enrollments.</p>
      </Main>
    )
  }

  return (
    <div className='space-y-4'>
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex items-center justify-between'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>Leave Enrollments</h2>
            <p className='text-muted-foreground'>
              {selectedEmployee
                ? `${selectedEmployee.first_name} ${selectedEmployee.last_name} · ${selectedYear} enrollments`
                : 'Select an employee to view and manage their leave enrollments'}
            </p>
          </div>
          {canAdd && (
            <Button data-testid='enroll-employee-button' onClick={() => setDialogOpen(true)} disabled={!selectedEmployeeId}>
              Enroll
            </Button>
          )}
        </div>
        <div className='flex items-center gap-2'>
          <Select value={selectedEmployeeId} onValueChange={setSelectedEmployeeId}>
            <SelectTrigger className='w-[300px]' data-testid='enrollment-employee-select'>
              <SelectValue placeholder='Select employee' />
            </SelectTrigger>
            <SelectContent>
              {employees.length === 0 ? (
                <SelectItem value='no-employees' disabled>
                  No employees
                </SelectItem>
              ) : (
                employees.map((emp) => (
                  <SelectItem key={emp.id} value={emp.id}>
                    {emp.employee_code} — {emp.first_name} {emp.last_name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          <Select value={selectedYear.toString()} onValueChange={(v) => setSelectedYear(Number(v))}>
            <SelectTrigger className='w-[160px]' data-testid='enrollment-year-select'>
              <SelectValue placeholder='Leave year' />
            </SelectTrigger>
            <SelectContent>
              {[...Array(7)].map((_, i) => {
                const year = 2024 + i
                return (
                  <SelectItem key={year} value={year.toString()}>
                    {year}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        </div>
        {(employeesPending || policiesPending) && <div className='text-sm text-muted-foreground'>Loading...</div>}
        {_enrollmentsPending && <div className='text-sm text-muted-foreground'>Loading enrollments…</div>}
        {isError && !_enrollmentsPending && (
          <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
            <p className='text-sm text-muted-foreground'>Failed to load enrollments.</p>
            <button
              type='button'
              onClick={() => refetch()}
              className='text-sm font-medium text-primary underline underline-offset-4'
            >
              Try again
            </button>
          </div>
        )}
        {!_enrollmentsPending && !isError && enrollmentsData && (
          <div className='overflow-x-auto rounded-lg border'>
            <table className='w-full text-sm'>
              <thead>
                <tr className='border-b bg-muted/50'>
                  <th className='p-2 text-left'>Leave Policy</th>
                  <th className='p-2 text-left'>Granted Days</th>
                  <th className='p-2 text-left'>Active</th>
                  <th className='p-2 text-left'>Transferred</th>
                </tr>
              </thead>
              <tbody>
                {enrollments.length === 0 ? (
                  <tr>
                    <td colSpan={4} className='p-4 text-center text-muted-foreground'>
                      No enrollments for this employee in {selectedYear}. Click &quot;Enroll&quot; to enroll one.
                    </td>
                  </tr>
                ) : (
                  enrollments.map((enrollment) => {
                    const policy = policies.find((p) => p.id === enrollment.policy_id)
                    return (
                      <tr key={enrollment.id} className='border-b hover:bg-muted/30'>
                        <td className='p-2'>
                          {policy ? (
                            <div className='flex flex-col'>
                              <span className='font-medium'>{policy.name}</span>
                              <span className='text-xs text-muted-foreground'>{policy.code}</span>
                            </div>
                          ) : (
                            <span className='text-muted-foreground'>—</span>
                          )}
                        </td>
                        <td className='p-2'>{enrollment.granted_days}</td>
                        <td className='p-2'>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              enrollment.is_active
                                ? 'bg-green-100 text-green-800'
                                : 'bg-gray-100 text-gray-800'
                            }`}
                          >
                            {enrollment.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className='p-2'>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              enrollment.is_transferred
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-gray-100 text-gray-800'
                            }`}
                          >
                            {enrollment.is_transferred ? 'Transferred' : 'No'}
                          </span>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </Main>
      <EnrollmentDialog
        key={dialogOpen ? `${selectedEmployeeId ?? 'none'}:${selectedYear}` : 'closed'}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        employeeId={selectedEmployeeId}
        leaveYear={selectedYear}
        availablePolicies={policies}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  )
}
