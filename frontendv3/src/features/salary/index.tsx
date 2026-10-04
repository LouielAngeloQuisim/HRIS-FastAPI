import { useState } from 'react'
import { useEmployeeSalaries } from '@/lib/api/payroll'
import { useEmployees } from '@/lib/api/employees'
import type { EmployeeSalaryPublic } from '@/lib/api/types'
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
import { SalaryForm } from './components/salary-form'

export default function SalaryPage() {
  const canView = useCan('payroll', 'view')
  const canAdd = useCan('payroll', 'add')
  const canEdit = useCan('payroll', 'edit')

  const [page] = useState(1)
  const pageSize = 500
  const { data: employeesData, isPending: employeesPending } = useEmployees(page, pageSize)
  const employees = employeesData?.data ?? []

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | undefined>(undefined)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<EmployeeSalaryPublic | null>(null)

  const { data, isPending, isError, refetch } = useEmployeeSalaries(selectedEmployeeId)

  const handleAdd = () => {
    setEditing(null)
    setFormOpen(true)
  }

  const handleEdit = (salary: EmployeeSalaryPublic) => {
    setEditing(salary)
    setFormOpen(true)
  }

  const handleClose = () => {
    setFormOpen(false)
    setEditing(null)
  }

  if (!canView) {
    return (
      <Main>
        <p className='text-muted-foreground'>You do not have permission to view salaries.</p>
      </Main>
    )
  }

  const selectedEmployee = employees.find((e) => e.id === selectedEmployeeId)

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
            <h2 className='text-2xl font-bold tracking-tight'>Employee Salaries</h2>
            <p className='text-muted-foreground'>
              {selectedEmployee
                ? `${selectedEmployee.first_name} ${selectedEmployee.last_name} · ${data?.count ?? 0} salary records`
                : 'Select an employee to view and manage their salary'}
            </p>
          </div>
          {(selectedEmployeeId || editing) && canAdd && (
            <Button data-testid='add-salary-button' onClick={handleAdd}>
              Add Salary
            </Button>
          )}
        </div>
        <div className='flex items-center gap-2'>
          <Select value={selectedEmployeeId} onValueChange={setSelectedEmployeeId}>
            <SelectTrigger className='w-[300px]' data-testid='salary-employee-select'>
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
        </div>
        {employeesPending && <div className='text-sm text-muted-foreground'>Loading employees…</div>}
        {isPending && <div className='text-sm text-muted-foreground'>Loading salaries…</div>}
        {isError && !isPending && (
          <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
            <p className='text-sm text-muted-foreground'>Failed to load salaries.</p>
            <button
              type='button'
              onClick={() => refetch()}
              className='text-sm font-medium text-primary underline underline-offset-4'
            >
              Try again
            </button>
          </div>
        )}
        {!isPending && !isError && data && (
          <div className='overflow-x-auto rounded-lg border'>
            <table className='w-full text-sm'>
              <thead>
                <tr className='border-b bg-muted/50'>
                  <th className='p-2 text-left'>Basic Rate</th>
                  <th className='p-2 text-left'>Pay Type</th>
                  <th className='p-2 text-left'>Effective Date</th>
                  <th className='p-2 text-left'>Currency</th>
                  <th className='p-2 text-left'>Status</th>
                  <th className='p-2 text-right'>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.data.length === 0 ? (
                  <tr>
                    <td colSpan={6} className='p-4 text-center text-muted-foreground'>
                      No salaries configured for this employee. Click &quot;Add Salary&quot; to configure one.
                    </td>
                  </tr>
                ) : (
                  data.data.map((salary) => (
                    <tr key={salary.id} className='border-b hover:bg-muted/30'>
                      <td className='p-2'>{salary.basic_rate}</td>
                      <td className='p-2'>{salary.pay_type ?? '—'}</td>
                      <td className='p-2'>{salary.effective_date}</td>
                      <td className='p-2'>{salary.currency ?? 'PHP'}</td>
                      <td className='p-2'>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            salary.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {salary.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className='p-2 text-right'>
                        {canEdit && (
                          <Button
                            variant='ghost'
                            size='sm'
                            data-testid={`edit-salary-button-${salary.id}`}
                            onClick={() => handleEdit(salary)}
                          >
                            Edit
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </Main>
      <SalaryForm
        key={formOpen ? (editing?.id ?? 'add') : 'closed'}
        open={formOpen}
        onClose={handleClose}
        employeeId={selectedEmployeeId ?? editing?.employee_id}
        initialData={editing ?? undefined}
      />
    </div>
  )
}
