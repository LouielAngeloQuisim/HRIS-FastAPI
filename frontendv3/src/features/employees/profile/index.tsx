import { useParams, Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useEmployee } from '@/lib/api/employees'
import { useCan } from '@/context/permissions-provider'
import { useEmployeePayGroupAssignments, useEmployeeSalaries } from '@/lib/api/payroll'
import { fullName, type Employee } from '../data/schema'
import { TaxYearDeclaration } from './tax-year-declaration'

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className='flex flex-col gap-0.5'>
      <dt className='text-xs text-muted-foreground'>{label}</dt>
      <dd className='text-sm font-medium'>{value || '—'}</dd>
    </div>
  )
}

function Overview({ employee }: { employee: Employee }) {
  return (
    <div className='grid gap-4 lg:grid-cols-3'>
      <Card className='lg:col-span-1'>
        <CardHeader>
          <CardTitle className='text-base'>Personal Information</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className='grid grid-cols-2 gap-4'>
            <Field label='Gender' value={employee.gender} />
            <Field label='Civil Status' value={employee.civil_status} />
            <Field
              label='Birthdate'
              value={
                employee.birthdate
                  ? new Date(employee.birthdate).toLocaleDateString()
                  : null
              }
            />
            <Field label='Birth Place' value={employee.birth_place} />
            <Field
              label='Date Hired'
              value={
                employee.date_hired
                  ? new Date(employee.date_hired).toLocaleDateString()
                  : null
              }
            />
            <Field label='Email' value={employee.email} />
            <Field label='Telephone' value={employee.telephone} />
            <Field label='Cellphone' value={employee.cellphone} />
          </dl>
        </CardContent>
      </Card>

      <Card className='lg:col-span-2'>
        <CardHeader>
          <CardTitle className='text-base'>Employment</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className='grid grid-cols-2 gap-4'>
            <Field label='Employee Code' value={employee.employee_code} />
            <Field label='Employment Type' value={employee.employment_type} />
            <Field label='Status' value={employee.employee_status} />
            <Field
              label='Contract Expiry'
              value={
                employee.contract_expiry_date
                  ? new Date(employee.contract_expiry_date).toLocaleDateString()
                  : null
              }
            />
            <Field
              label='Probationary Date'
              value={
                employee.probationary_date
                  ? new Date(employee.probationary_date).toLocaleDateString()
                  : null
              }
            />
            <Field
              label='Regularization Date'
              value={
                employee.regularization_date
                  ? new Date(employee.regularization_date).toLocaleDateString()
                  : null
              }
            />
            <Field
              label='Date Separated'
              value={
                employee.date_separated
                  ? new Date(employee.date_separated).toLocaleDateString()
                  : null
              }
            />
            <Field label='Present Address' value={employee.present_barangay && employee.present_city ? `${employee.present_barangay}, ${employee.present_city}` : null} />
            <Field label='Permanent Address' value={employee.permanent_barangay && employee.permanent_city ? `${employee.permanent_barangay}, ${employee.permanent_city}` : null} />
          </dl>
          <p className='mt-4 text-xs text-muted-foreground'>
            Government IDs, education, dependents and other 201-file sections are
            not yet available in this view.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function Compensation({ employeeId }: { employeeId: string }) {
  const salaries = useEmployeeSalaries(employeeId)
  const assignments = useEmployeePayGroupAssignments(employeeId)
  const canViewPayroll = useCan('payroll', 'view')
  if (!canViewPayroll) return null
  const salaryRows = salaries.data?.data ?? []
  const latest = [...salaryRows].sort((a, b) => b.effective_date.localeCompare(a.effective_date))[0]
  return <Card>
    <CardHeader><CardTitle className='text-base'>Compensation and payroll setup</CardTitle></CardHeader>
    <CardContent className='space-y-3'>
      {salaries.isPending || assignments.isPending ? <p className='text-sm text-muted-foreground'>Loading compensation…</p> : salaries.isError || assignments.isError ? <p role='alert' className='text-sm text-destructive'>Compensation details could not be loaded.</p> : latest ? <>
        <dl className='grid grid-cols-2 gap-4'>
          <Field label='Salary basis' value={latest.pay_type} />
          <Field label='Basic rate' value={`${latest.currency} ${latest.basic_rate}`} />
          <Field label='Effective from' value={latest.effective_date} />
          <Field label='Non-taxable allowance' value={`${latest.currency} ${latest.non_taxable_allowance}`} />
        </dl>
        <div><h3 className='text-sm font-medium'>Pay group history</h3>{assignments.data?.length ? assignments.data.map(row => <p key={row.id} className='text-sm text-muted-foreground'>{row.effective_from}{row.effective_to ? ` through ${row.effective_to}` : ' onward'} · group {row.pay_group_id}</p>) : <p className='text-sm text-muted-foreground'>No pay group is assigned.</p>}</div>
        <p className='text-xs text-muted-foreground'>Contribution amounts and tax are calculated for each payroll period from applicable rules and employee history; this profile does not treat them as fixed salary deductions.</p>
      </> : <p className='text-sm text-muted-foreground'>No salary is configured for this employee.</p>}
    </CardContent>
  </Card>
}

export function EmployeeProfile() {
  const { employeeId } = useParams({ from: '/_authenticated/employees/$employeeId' })
  const { data, isPending, isError } = useEmployee(employeeId)
  const canViewPayroll = useCan('payroll', 'view')

  return (
    <div className='flex flex-col gap-4 p-4 sm:p-6'>
      <Button variant='ghost' size='sm' asChild className='w-fit'>
        <Link to='/employees' search={{}}>
          <ArrowLeft className='h-4 w-4' />
          Back to employees
        </Link>
      </Button>

      {isPending ? (
        <Skeleton className='h-64 w-full' />
      ) : isError || !data ? (
        <p className='text-sm text-muted-foreground'>
          Could not load this employee.
        </p>
      ) : (
        <>
          <div className='flex flex-col gap-1'>
            <h1 className='text-2xl font-bold tracking-tight'>
              {fullName(data)}
            </h1>
            <p className='text-sm text-muted-foreground'>
              {data.employee_code}
            </p>
          </div>
          <Overview employee={data} />
          <Compensation employeeId={data.id} />
          {canViewPayroll ? <TaxYearDeclaration employeeId={data.id} taxYear={new Date().getFullYear()} /> : null}
        </>
      )}
    </div>
  )
}
