import { type ColumnDef } from '@tanstack/react-table'
import { Link } from '@tanstack/react-router'
import { Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { type Employee, fullName } from '../data/schema'
import { useEmployeesActions } from './employees-actions'

// Re-export actions context so consumers of employees-columns can use it.
export { EmployeesActionsProvider, useEmployeesActions } from './employees-actions'

export const employeesColumns: ColumnDef<Employee>[] = [
  {
    accessorKey: 'employee_code',
    header: 'Employee Code',
    cell: ({ row }) => (
      <span className='ps-2 font-medium'>{row.getValue('employee_code')}</span>
    ),
    enableHiding: false,
  },
  {
    id: 'name',
    header: 'Name',
    cell: ({ row }) => (
      <Link
        to='/employees/$employeeId'
        params={{ employeeId: row.original.id }}
        className='font-medium text-foreground hover:underline'
      >
        {fullName(row.original)}
      </Link>
    ),
  },
  {
    accessorKey: 'division_id',
    header: 'Division',
    cell: ({ row }) => {
      const v = row.getValue('division_id') as string | null
      return <span className='text-muted-foreground'>{v ? v.slice(0, 8) : '—'}</span>
    },
  },
  {
    accessorKey: 'department_id',
    header: 'Department',
    cell: ({ row }) => {
      const v = row.getValue('department_id') as string | null
      return <span className='text-muted-foreground'>{v ? v.slice(0, 8) : '—'}</span>
    },
  },
  {
    accessorKey: 'employment_type',
    header: 'Employment Type',
    cell: ({ row }) => (
      <span>{row.getValue('employment_type') ?? '—'}</span>
    ),
  },
  {
    accessorKey: 'date_hired',
    header: 'Date Hired',
    cell: ({ row }) => {
      const v = row.getValue('date_hired') as string | null
      return <span>{v ? new Date(v).toLocaleDateString() : '—'}</span>
    },
  },
  {
    accessorKey: 'employee_status',
    header: 'Status',
    cell: ({ row }) => (
      <Badge variant='outline' className='capitalize'>
        {row.getValue('employee_status')}
      </Badge>
    ),
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
    enableSorting: false,
  },
  {
    id: 'actions',
    header: () => <div className='text-right'>Actions</div>,
    cell: ({ row }) => <EmployeeActionsCell employee={row.original} />,
    enableSorting: false,
    enableHiding: false,
  },
]

function EmployeeActionsCell({ employee }: { employee: Employee }) {
  const { onEdit, onDelete, deletePending } = useEmployeesActions()
  return (
    <div className='flex justify-end gap-1'>
      <Button variant='ghost' size='icon' asChild aria-label='View employee'>
        <Link
          to='/employees/$employeeId'
          params={{ employeeId: employee.id }}
        >
          <Eye className='h-4 w-4' />
        </Link>
      </Button>
      <Button
        variant='ghost'
        size='sm'
        data-testid={`edit-employee-button-${employee.id}`}
        onClick={() => onEdit?.(employee)}
      >
        Edit
      </Button>
      <Button
        variant='ghost'
        size='sm'
        className='text-destructive hover:text-destructive'
        data-testid={`archive-employee-button-${employee.id}`}
        onClick={() => onDelete?.(employee)}
        disabled={deletePending}
      >
        Archive
      </Button>
    </div>
  )
}
