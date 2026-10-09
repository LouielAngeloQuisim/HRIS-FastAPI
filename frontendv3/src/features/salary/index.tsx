import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { useEmployees } from '@/lib/api/employees'
import {
  useBulkPayGroupAssignments,
  useBulkSalary,
  useBulkSalaryIncrement,
  useEmployeeSalaries,
  usePayGroupList,
  useSalaryRoster,
} from '@/lib/api/payroll'
import { saveErrorMessage } from '@/lib/api/save-error'
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

  const [employeePage, setEmployeePage] = useState(1)
  const [incrementPage, setIncrementPage] = useState(1)
  const [incrementSearch, setIncrementSearch] = useState('')
  const [appliedIncrementSearch, setAppliedIncrementSearch] = useState('')
  const pageSize = 500
  const { data: employeesData, isPending: employeesPending } = useEmployees(
    1,
    pageSize
  )
  const { data: bulkEmployeesData, isPending: bulkEmployeesPending } =
    useEmployees(employeePage, pageSize)
  const employees = useMemo(
    () => employeesData?.data ?? [],
    [employeesData?.data]
  )
  const bulkEmployees = useMemo(
    () => bulkEmployeesData?.data ?? [],
    [bulkEmployeesData?.data]
  )
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<
    string | undefined
  >(undefined)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<EmployeeSalaryPublic | null>(null)
  const [missingSalaryOnly, setMissingSalaryOnly] = useState(false)
  const salaryRoster = useSalaryRoster(missingSalaryOnly)
  const incrementSalaryRoster = useSalaryRoster(
    false,
    (incrementPage - 1) * pageSize,
    pageSize,
    appliedIncrementSearch
  )
  const bulk = useBulkSalary()
  const increment = useBulkSalaryIncrement()
  const payGroups = usePayGroupList()
  const payGroupBulk = useBulkPayGroupAssignments()
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
  const [incrementSelected, setIncrementSelected] = useState<Record<string, boolean>>({})
  const [incrementAmount, setIncrementAmount] = useState('50.00')
  const [incrementDate, setIncrementDate] = useState('')
  const [incrementBatchId, setIncrementBatchId] = useState(crypto.randomUUID())
  const [incrementPreview, setIncrementPreview] = useState<{
    batchId: string
    valid: boolean
    changes: Array<{ employee_id: string; employee_code: string; employee_name: string; current_rate: string; proposed_rate: string; pay_type: string }>
    issues: Array<{ employee_id: string; code: string; message: string }>
  } | null>(null)
  const [payGroupSelected, setPayGroupSelected] = useState<
    Record<string, (typeof employees)[number]>
  >({})
  const [bulkPayGroupId, setBulkPayGroupId] = useState('')
  const [bulkPayGroupDate, setBulkPayGroupDate] = useState('')
  const [payGroupBatchId, setPayGroupBatchId] = useState(crypto.randomUUID())
  const [payGroupPreflight, setPayGroupPreflight] = useState<{
    batchId: string
    valid: boolean
    issues: Array<{ employee_id: string; code: string; message: string }>
  } | null>(null)

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
  const selectedIncrementIds = useMemo(
    () => Object.entries(incrementSelected).filter(([, selected]) => selected).map(([id]) => id),
    [incrementSelected]
  )
  const incrementEmployeeOptions = useMemo(
    () => (incrementSalaryRoster.data?.data ?? []).map(row => ({
          id: row.employee_id,
          employee_code: row.employee_code,
          first_name: row.first_name,
          last_name: row.last_name,
        })),
    [incrementSalaryRoster.data?.data]
  )
  const incrementEmployeeCount = incrementSalaryRoster.data?.count ?? 0
  const activeEmployees = useMemo(
    () =>
      bulkEmployees.filter((employee) => employee.employee_status === 'Active'),
    [bulkEmployees]
  )
  const selectedPayGroupEmployees = useMemo(
    () =>
      Object.values(payGroupSelected).filter(
        (employee) => employee.employee_status === 'Active'
      ),
    [payGroupSelected]
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
  const resetIncrementPreview = () => {
    setIncrementBatchId(crypto.randomUUID())
    setIncrementPreview(null)
  }
  const incrementRequest = () => ({
    batch_id: incrementBatchId,
    effective_date: incrementDate,
    increment: incrementAmount,
    employee_ids: selectedIncrementIds,
  })
  const handleIncrementPreview = async () => {
    try {
      const result = await increment.preview.mutateAsync(incrementRequest())
      setIncrementPreview({
        batchId: result.batch_id,
        valid: result.valid,
        changes: result.changes,
        issues: result.issues,
      })
      if (result.valid) toast.success(`${result.changes.length} salary changes are ready to review.`)
      else toast.error(`${result.issues.length} salary increment issue(s) found.`)
    } catch (error) {
      setIncrementPreview(null)
      toast.error(saveErrorMessage(error))
    }
  }
  const handleIncrementSearch = () => {
    setIncrementPage(1)
    setAppliedIncrementSearch(incrementSearch.trim())
  }
  const handleIncrementCommit = async () => {
    try {
      const result = await increment.commit.mutateAsync(incrementRequest())
      toast.success(`${result.salaries.length} salary increments saved${result.replayed ? ' (recovered saved result)' : ''}.`)
      setIncrementSelected({})
      resetIncrementPreview()
    } catch (error) {
      toast.error(`${saveErrorMessage(error)} Keep the same selection and retry with the same batch ID if the result is uncertain.`)
    }
  }
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

  const payGroupRequest = () => ({
    batch_id: payGroupBatchId,
    pay_group_id: bulkPayGroupId,
    effective_from: bulkPayGroupDate,
    employee_ids: selectedPayGroupEmployees.map((employee) => employee.id),
  })
  const resetPayGroupBatch = () => {
    setPayGroupBatchId(crypto.randomUUID())
    setPayGroupPreflight(null)
  }
  const handlePayGroupPreflight = async () => {
    try {
      const result = await payGroupBulk.preflight.mutateAsync(payGroupRequest())
      setPayGroupPreflight({
        batchId: result.batch_id,
        valid: result.valid,
        issues: result.issues,
      })
      if (result.valid) {
        toast.success(
          `${result.requested} selected employees are ready to assign.`
        )
      } else {
        toast.error(
          `${result.issues.length} pay-group assignment issue(s) found.`
        )
      }
    } catch (error) {
      setPayGroupPreflight(null)
      toast.error(saveErrorMessage(error))
    }
  }
  const handlePayGroupCommit = async () => {
    try {
      const result = await payGroupBulk.commit.mutateAsync(payGroupRequest())
      toast.success(
        `${result.assignments.length} employees assigned${result.replayed ? ' (recovered saved result)' : ''}.`
      )
      setPayGroupSelected({})
      resetPayGroupBatch()
    } catch (error) {
      toast.error(
        `${saveErrorMessage(error)} Keep this selection and retry with the same batch ID if the result is uncertain.`
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
                setBulkSelected({})
                setIncrementSelected({})
                setIncrementPage(1)
                resetIncrementPreview()
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
        {canEdit && (
          <section className='space-y-3 rounded-lg border p-4' aria-label='Bulk salary increment'>
            <div>
              <h3 className='font-semibold'>Bulk salary increase</h3>
              <p className='text-sm text-muted-foreground'>Select employees explicitly, choose an effective date and a shared increase. The amount is added to each selected employee’s existing rate: for example, ₱50 per month, per day or per hour according to that employee’s salary basis. The preview shows each current and proposed rate; allowances and overtime rates stay unchanged.</p>
            </div>
            <div className='flex flex-wrap items-end gap-3'>
              <label className='grid gap-1 text-sm'>Filter employees by code or name
                <input aria-label='Salary increment employee search' value={incrementSearch} onChange={event => setIncrementSearch(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') handleIncrementSearch() }} className='h-9 rounded-md border bg-background px-3' placeholder='Employee code or name' />
              </label>
              <Button type='button' variant='outline' data-testid='salary-increment-search' onClick={handleIncrementSearch}>Apply filter</Button>
              <label className='grid gap-1 text-sm'>Increase per existing rate (PHP)
                <input aria-label='Salary increase amount' type='number' min='0.01' step='0.01' value={incrementAmount} onChange={event => { setIncrementAmount(event.target.value); resetIncrementPreview() }} className='h-9 rounded-md border bg-background px-3' />
              </label>
              <label className='grid gap-1 text-sm'>Effective date
                <input aria-label='Salary increase effective date' type='date' value={incrementDate} onChange={event => { setIncrementDate(event.target.value); resetIncrementPreview() }} className='h-9 rounded-md border bg-background px-3' />
              </label>
              <span className='text-sm text-muted-foreground'>{selectedIncrementIds.length} employees explicitly selected</span>
              {selectedIncrementIds.length > 200 ? (
                <span role='alert' className='text-sm text-destructive'>A salary increment batch can include at most 200 employees. Remove some selections before continuing.</span>
              ) : null}
            </div>
            {incrementEmployeeCount > pageSize ? (
              <div className='flex items-center gap-2 text-sm'>
                <Button type='button' variant='outline' data-testid='salary-increment-previous-page' disabled={incrementPage <= 1 || incrementSalaryRoster.isPending} onClick={() => setIncrementPage(page => Math.max(1, page - 1))}>Previous employees</Button>
                <span>Page {incrementPage} of {Math.max(1, Math.ceil(incrementEmployeeCount / pageSize))}; selections remain checked across pages.</span>
                <Button type='button' variant='outline' data-testid='salary-increment-next-page' disabled={incrementSalaryRoster.isPending || incrementPage * pageSize >= incrementEmployeeCount} onClick={() => setIncrementPage(page => page + 1)}>Next employees</Button>
              </div>
            ) : null}
            <div className='max-h-64 overflow-auto rounded border'>
              {incrementEmployeeOptions.map(emp => (
                <label key={emp.id} className='flex items-center gap-2 border-b p-2 text-sm last:border-b-0'>
                  <input aria-label={`Select ${emp.employee_code} for increase`} type='checkbox' checked={Boolean(incrementSelected[emp.id])} onChange={event => { setIncrementSelected(current => ({ ...current, [emp.id]: event.target.checked })); resetIncrementPreview() }} />
                  <span>{emp.employee_code} — {emp.first_name} {emp.last_name}</span>
                </label>
              ))}
              {!incrementEmployeeOptions.length ? <p className='p-3 text-sm text-muted-foreground'>{incrementSalaryRoster.isPending ? 'Loading employees…' : 'No employees match the current salary roster filter.'}</p> : null}
            </div>
            <div className='flex flex-wrap gap-2'>
              <Button type='button' variant='outline' data-testid='salary-increment-preview' disabled={!selectedIncrementIds.length || selectedIncrementIds.length > 200 || !incrementDate || !Number.isFinite(Number(incrementAmount)) || Number(incrementAmount) <= 0 || increment.preview.isPending || increment.commit.isPending} onClick={handleIncrementPreview}>{increment.preview.isPending ? 'Calculating…' : 'Preview increase'}</Button>
              <Button type='button' data-testid='salary-increment-commit' disabled={!incrementPreview?.valid || incrementPreview.batchId !== incrementBatchId || increment.commit.isPending} onClick={handleIncrementCommit}>{increment.commit.isPending ? 'Saving…' : increment.commit.isError ? 'Retry same batch' : 'Apply selected increase'}</Button>
            </div>
            {incrementPreview?.changes.map(change => {
              return <p key={change.employee_id} className='text-sm'>{change.employee_code} — {change.employee_name}: ₱{change.current_rate} → ₱{change.proposed_rate} ({change.pay_type})</p>
            })}
            {incrementPreview?.issues.map(issue => <p key={`${issue.employee_id}-${issue.code}`} role='alert' className='text-sm text-destructive'>{incrementEmployeeOptions.find(row => row.id === issue.employee_id)?.employee_code ?? issue.employee_id}: {issue.message}</p>)}
          </section>
        )}
        {canAdd && (
          <section
            className='space-y-3 rounded-lg border p-4'
            aria-label='Bulk pay-group assignment'
          >
            <div>
              <h3 className='font-semibold'>Bulk pay-group assignment</h3>
              <p className='text-sm text-muted-foreground'>
                Choose specific active employees and one effective date. A
                transfer closes the current assignment the day before the new
                period starts. Monthly and twice-monthly changes must start at a
                boundary shared by the current and target groups.
              </p>
            </div>
            <div className='grid gap-3 md:grid-cols-2'>
              <label className='grid gap-1 text-sm'>
                Target pay group
                <Select
                  value={bulkPayGroupId}
                  onValueChange={(value) => {
                    setBulkPayGroupId(value)
                    resetPayGroupBatch()
                  }}
                >
                  <SelectTrigger data-testid='bulk-pay-group-select'>
                    <SelectValue placeholder='Select pay group' />
                  </SelectTrigger>
                  <SelectContent>
                    {(payGroups.data ?? [])
                      .filter((group) => group.is_active)
                      .map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {group.name} · {group.cadence.replace('_', ' ')}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </label>
              <label className='grid gap-1 text-sm'>
                Effective from
                <input
                  data-testid='bulk-pay-group-effective-date'
                  aria-label='Pay-group effective date'
                  type='date'
                  value={bulkPayGroupDate}
                  onChange={(event) => {
                    setBulkPayGroupDate(event.target.value)
                    resetPayGroupBatch()
                  }}
                  className='h-9 rounded-md border bg-background px-3'
                />
              </label>
            </div>
            {payGroups.isError ? (
              <p role='alert' className='text-sm text-destructive'>
                Pay groups could not be loaded.
              </p>
            ) : null}
            {!bulkEmployeesPending &&
            (bulkEmployeesData?.count ?? 0) > pageSize ? (
              <p className='text-sm text-amber-700'>
                Select employees across pages; checked employees remain
                selected.
              </p>
            ) : null}
            <div className='flex items-center gap-2 text-sm'>
              <Button
                type='button'
                variant='outline'
                disabled={employeePage <= 1 || bulkEmployeesPending}
                onClick={() =>
                  setEmployeePage((current) => Math.max(1, current - 1))
                }
              >
                Previous employees
              </Button>
              <span>
                Page {employeePage} of{' '}
                {Math.max(
                  1,
                  Math.ceil((bulkEmployeesData?.count ?? 0) / pageSize)
                )}
              </span>
              <Button
                type='button'
                variant='outline'
                data-testid='pay-group-next-page'
                disabled={
                  bulkEmployeesPending ||
                  employeePage * pageSize >= (bulkEmployeesData?.count ?? 0)
                }
                onClick={() => setEmployeePage((current) => current + 1)}
              >
                Next employees
              </Button>
            </div>
            <div className='max-h-72 overflow-auto rounded border'>
              {activeEmployees.map((employee) => (
                <label
                  key={employee.id}
                  className='flex items-center gap-2 border-b p-2 text-sm last:border-b-0'
                >
                  <input
                    aria-label={`Assign ${employee.employee_code}`}
                    type='checkbox'
                    checked={Boolean(payGroupSelected[employee.id])}
                    onChange={(event) => {
                      const checked = event.target.checked
                      setPayGroupSelected((current) => {
                        const next = { ...current }
                        if (checked) next[employee.id] = employee
                        else delete next[employee.id]
                        return next
                      })
                      resetPayGroupBatch()
                    }}
                  />
                  <span>
                    {employee.employee_code} — {employee.first_name}{' '}
                    {employee.last_name}
                  </span>
                </label>
              ))}
              {!activeEmployees.length ? (
                <p className='p-3 text-sm text-muted-foreground'>
                  No active employees are available.
                </p>
              ) : null}
            </div>
            <div className='flex flex-wrap items-center gap-2'>
              <span className='text-sm text-muted-foreground'>
                {selectedPayGroupEmployees.length} employees explicitly selected
              </span>
              {selectedPayGroupEmployees.length > 200 ? (
                <span role='alert' className='text-sm text-destructive'>
                  A batch can include at most 200 employees. Remove some
                  selections before continuing.
                </span>
              ) : null}
              <Button
                type='button'
                variant='outline'
                data-testid='pay-group-bulk-preflight'
                disabled={
                  !selectedPayGroupEmployees.length ||
                  selectedPayGroupEmployees.length > 200 ||
                  !bulkPayGroupId ||
                  !bulkPayGroupDate ||
                  payGroupBulk.preflight.isPending ||
                  payGroupBulk.commit.isPending
                }
                onClick={handlePayGroupPreflight}
              >
                {payGroupBulk.preflight.isPending
                  ? 'Checking assignments…'
                  : 'Validate selected employees'}
              </Button>
              <Button
                type='button'
                data-testid='pay-group-bulk-commit'
                disabled={
                  !payGroupPreflight?.valid ||
                  payGroupPreflight.batchId !== payGroupBatchId ||
                  payGroupBulk.commit.isPending
                }
                onClick={handlePayGroupCommit}
              >
                {payGroupBulk.commit.isPending
                  ? 'Saving assignments…'
                  : payGroupBulk.commit.isError
                    ? 'Retry same batch'
                    : 'Assign selected employees'}
              </Button>
            </div>
            {payGroupPreflight?.issues.map((issue) => {
              const employee =
                activeEmployees.find((row) => row.id === issue.employee_id) ??
                payGroupSelected[issue.employee_id]
              return (
                <p
                  key={`${issue.employee_id}-${issue.code}`}
                  role='alert'
                  className='text-sm text-destructive'
                >
                  {employee?.employee_code ?? issue.employee_id}:{' '}
                  {issue.message}
                </p>
              )
            })}
            {payGroupBulk.commit.isError ? (
              <p role='status' className='text-sm text-amber-700'>
                The result may be uncertain. Keep this selection unchanged and
                retry with the same batch ID to recover without duplicate
                assignments.
              </p>
            ) : null}
          </section>
        )}
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
                      aria-label={`${emp.employee_code} fixed monthly allowance`}
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
                      placeholder='Fixed monthly allowance'
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
                  Enter a positive basic rate and non-negative overtime and
                  fixed monthly allowance for each selected employee.
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
