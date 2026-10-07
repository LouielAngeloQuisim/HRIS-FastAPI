import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { useEmployees } from '@/lib/api/employees'
import {
  useBulkSalary,
  useEmployeeSalaries,
  useSalaryRoster,
} from '@/lib/api/payroll'
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
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { SalaryForm } from './components/salary-form'

export default function SalaryPage() {
  const canView = useCan('payroll', 'view')
  const canAdd = useCan('payroll', 'add')
  const canEdit = useCan('payroll', 'edit')

  const [page] = useState(1)
  const pageSize = 500
  const { data: employeesData, isPending: employeesPending } = useEmployees(
    page,
    pageSize
  )
  const employees = employeesData?.data ?? []

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<
    string | undefined
  >(undefined)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<EmployeeSalaryPublic | null>(null)
  const [missingSalaryOnly, setMissingSalaryOnly] = useState(false)
  const salaryRoster = useSalaryRoster(missingSalaryOnly)
  const bulk = useBulkSalary()
  const [bulkSelected, setBulkSelected] = useState<Record<string, boolean>>({})
  const [bulkRates, setBulkRates] = useState<
    Record<
      string,
      {
        basic_rate: string
        pay_type: 'hourly' | 'daily' | 'monthly'
        overtime_rate: string
        non_taxable_allowance: string
      }
    >
  >({})
  const [bulkEffectiveDate, setBulkEffectiveDate] = useState('')
  const [bulkBatchId, setBulkBatchId] = useState(crypto.randomUUID())

  const { data, isPending, isError, refetch } =
    useEmployeeSalaries(selectedEmployeeId)

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

  const employeeOptions = missingSalaryOnly
    ? (salaryRoster.data?.data ?? []).map((row) => ({
        id: row.employee_id,
        employee_code: row.employee_code,
        first_name: row.first_name,
        last_name: row.last_name,
      }))
    : employees
  const selectedEmployee = employeeOptions.find(
    (e) => e.id === selectedEmployeeId
  )
  const selectedBulkEmployees = useMemo(
    () => employeeOptions.filter((emp) => bulkSelected[emp.id]),
    [employeeOptions, bulkSelected]
  )
  const invalidBulkEmployees = selectedBulkEmployees.filter((emp) => {
    const rates = bulkRates[emp.id]
    return (
      !rates ||
      !Number.isFinite(Number(rates.basic_rate)) ||
      Number(rates.basic_rate) <= 0 ||
      !Number.isFinite(Number(rates.overtime_rate)) ||
      Number(rates.overtime_rate) < 0 ||
      !Number.isFinite(Number(rates.non_taxable_allowance)) ||
      Number(rates.non_taxable_allowance) < 0
    )
  })

  if (!canView) {
    return (
      <Main>
        <p className='text-muted-foreground'>
          You do not have permission to view salaries.
        </p>
      </Main>
    )
  }

  const bulkRequest = () => ({
    batch_id: bulkBatchId,
    effective_date: bulkEffectiveDate,
    rows: selectedBulkEmployees.map((emp) => ({
      employee_id: emp.id,
      basic_rate: bulkRates[emp.id]?.basic_rate ?? '',
      pay_type: bulkRates[emp.id]?.pay_type ?? 'monthly',
      overtime_rate: bulkRates[emp.id]?.overtime_rate ?? '0',
      non_taxable_allowance: bulkRates[emp.id]?.non_taxable_allowance ?? '0',
    })),
  })

  const resetBulkBatch = () => setBulkBatchId(crypto.randomUUID())
  const handleBulkPreflight = async () => {
    try {
      const result = await bulk.preflight.mutateAsync(bulkRequest())
      if (result.valid)
        toast.success(`${result.requested} salary rows are ready to save.`)
      else toast.error(result.issues.map((issue) => issue.message).join(' '))
    } catch {
      toast.error('Salary preflight failed. No salaries were saved.')
    }
  }
  const handleBulkCommit = async () => {
    try {
      const result = await bulk.commit.mutateAsync(bulkRequest())
      toast.success(
        `${result.salaries.length} salary records saved${result.replayed ? ' (recovered existing result)' : ''}.`
      )
      setBulkSelected({})
      resetBulkBatch()
    } catch {
      toast.error(
        'Save result is uncertain or blocked. Keep this batch ID and reconcile before starting another batch.'
      )
    }
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
            <h2 className='text-2xl font-bold tracking-tight'>
              Employee Salaries
            </h2>
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
          <label className='flex items-center gap-2 text-sm'>
            <input
              type='checkbox'
              checked={missingSalaryOnly}
              onChange={(event) => {
                setMissingSalaryOnly(event.target.checked)
                setSelectedEmployeeId(undefined)
              }}
            />
            Only employees without an effective salary
          </label>
          {missingSalaryOnly && (
            <span className='text-xs text-muted-foreground'>
              {salaryRoster.data?.count ?? 0} employees need salary setup
            </span>
          )}
          <Select
            value={selectedEmployeeId}
            onValueChange={setSelectedEmployeeId}
          >
            <SelectTrigger
              className='w-[300px]'
              data-testid='salary-employee-select'
            >
              <SelectValue
                placeholder={
                  missingSalaryOnly
                    ? 'Select employee without salary'
                    : 'Select employee'
                }
              />
            </SelectTrigger>
            <SelectContent>
              {employeeOptions.length === 0 ? (
                <SelectItem value='no-employees' disabled>
                  {missingSalaryOnly
                    ? 'No missing salary records'
                    : 'No employees'}
                </SelectItem>
              ) : (
                employeeOptions.map((emp) => (
                  <SelectItem key={emp.id} value={emp.id}>
                    {emp.employee_code} — {emp.first_name} {emp.last_name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
        {canAdd && (
          <section
            className='space-y-3 rounded-lg border p-4'
            aria-label='Bulk salary setup'
          >
            <div>
              <h3 className='font-semibold'>Bulk salary setup</h3>
              <p className='text-sm text-muted-foreground'>
                Select employees explicitly, set each rate, then validate and
                save the batch.
              </p>
            </div>
            <label className='flex items-center gap-2 text-sm'>
              Shared effective date
              <input
                aria-label='Bulk effective date'
                type='date'
                value={bulkEffectiveDate}
                onChange={(event) => {
                  setBulkEffectiveDate(event.target.value)
                  resetBulkBatch()
                }}
                className='rounded border bg-background px-2 py-1'
              />
            </label>
            <div className='max-h-80 overflow-auto rounded border'>
              {employeeOptions.map((emp) => {
                const rates = bulkRates[emp.id] ?? {
                  basic_rate: '',
                  pay_type: 'monthly' as const,
                  overtime_rate: '0',
                  non_taxable_allowance: '0',
                }
                return (
                  <div
                    key={emp.id}
                    className='grid grid-cols-[auto_1fr_repeat(4,minmax(6rem,8rem))] items-center gap-2 border-b p-2 text-sm'
                  >
                    <input
                      aria-label={`Select ${emp.employee_code}`}
                      type='checkbox'
                      checked={Boolean(bulkSelected[emp.id])}
                      onChange={(event) => {
                        setBulkSelected((current) => ({
                          ...current,
                          [emp.id]: event.target.checked,
                        }))
                        resetBulkBatch()
                      }}
                    />
                    <span>
                      {emp.employee_code} — {emp.first_name} {emp.last_name}
                    </span>
                    <input
                      aria-label={`${emp.employee_code} basic rate`}
                      type='number'
                      min='0.01'
                      step='0.01'
                      value={rates.basic_rate}
                      onChange={(event) => {
                        setBulkRates((current) => ({
                          ...current,
                          [emp.id]: {
                            ...rates,
                            basic_rate: event.target.value,
                          },
                        }))
                        resetBulkBatch()
                      }}
                      placeholder='Basic rate'
                      className='w-full rounded border bg-background px-2 py-1'
                    />
                    <select
                      aria-label={`${emp.employee_code} salary basis`}
                      value={rates.pay_type}
                      onChange={(event) => {
                        setBulkRates((current) => ({
                          ...current,
                          [emp.id]: {
                            ...rates,
                            pay_type: event.target
                              .value as typeof rates.pay_type,
                          },
                        }))
                        resetBulkBatch()
                      }}
                      className='rounded border bg-background px-2 py-1'
                    >
                      <option value='monthly'>Monthly</option>
                      <option value='daily'>Daily</option>
                      <option value='hourly'>Hourly</option>
                    </select>
                    <input
                      aria-label={`${emp.employee_code} overtime rate`}
                      type='number'
                      min='0'
                      step='0.001'
                      value={rates.overtime_rate}
                      onChange={(event) => {
                        setBulkRates((current) => ({
                          ...current,
                          [emp.id]: {
                            ...rates,
                            overtime_rate: event.target.value,
                          },
                        }))
                        resetBulkBatch()
                      }}
                      placeholder='OT rate'
                      className='w-full rounded border bg-background px-2 py-1'
                    />
                    <input
                      aria-label={`${emp.employee_code} allowance`}
                      type='number'
                      min='0'
                      step='0.01'
                      value={rates.non_taxable_allowance}
                      onChange={(event) => {
                        setBulkRates((current) => ({
                          ...current,
                          [emp.id]: {
                            ...rates,
                            non_taxable_allowance: event.target.value,
                          },
                        }))
                        resetBulkBatch()
                      }}
                      placeholder='Allowance'
                      className='w-full rounded border bg-background px-2 py-1'
                    />
                  </div>
                )
              })}
              {employeeOptions.length === 0 && (
                <p className='p-3 text-sm text-muted-foreground'>
                  No employees available in this roster.
                </p>
              )}
            </div>
            <div className='flex items-center gap-2'>
              <span className='text-sm text-muted-foreground'>
                {selectedBulkEmployees.length} explicitly selected
              </span>
              {invalidBulkEmployees.length > 0 && (
                <span role='alert' className='text-xs text-destructive'>
                  Enter a positive basic rate and non-negative
                  overtime/allowance for each selected employee.
                </span>
              )}
              <Button
                type='button'
                variant='outline'
                disabled={
                  !selectedBulkEmployees.length ||
                  invalidBulkEmployees.length > 0 ||
                  !bulkEffectiveDate ||
                  bulk.preflight.isPending ||
                  bulk.commit.isPending
                }
                onClick={handleBulkPreflight}
              >
                Validate batch
              </Button>
              <Button
                type='button'
                disabled={
                  !selectedBulkEmployees.length ||
                  invalidBulkEmployees.length > 0 ||
                  !bulkEffectiveDate ||
                  bulk.commit.isPending ||
                  bulk.preflight.isPending
                }
                onClick={handleBulkCommit}
              >
                Save selected salaries
              </Button>
            </div>
          </section>
        )}
        {employeesPending && (
          <div className='text-sm text-muted-foreground'>
            Loading employees…
          </div>
        )}
        {isPending && (
          <div className='text-sm text-muted-foreground'>Loading salaries…</div>
        )}
        {isError && !isPending && (
          <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
            <p className='text-sm text-muted-foreground'>
              Failed to load salaries.
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
                    <td
                      colSpan={6}
                      className='p-4 text-center text-muted-foreground'
                    >
                      No salaries configured for this employee. Click &quot;Add
                      Salary&quot; to configure one.
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
        employeeId={selectedEmployeeId ?? editing?.employee_id ?? ''}
        initialData={editing ?? undefined}
      />
    </div>
  )
}
