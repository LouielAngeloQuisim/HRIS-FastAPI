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
import { fullName, type Employee } from '../data/schema'

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

export function EmployeeProfile() {
  const { employeeId } = useParams({ from: '/_authenticated/employees/$employeeId' })
  const { data, isPending, isError } = useEmployee(employeeId)

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
        </>
      )}
    </div>
  )
}
