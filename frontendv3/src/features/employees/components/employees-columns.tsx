import { type ColumnDef } from '@tanstack/react-table'
import { Link } from '@tanstack/react-router'
import { Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { type Employee, fullName } from '../data/schema'

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
    cell: ({ row }) => (
      <div className='flex justify-end'>
        <Button variant='ghost' size='icon' asChild>
          <Link
            to='/employees/$employeeId'
            params={{ employeeId: row.original.id }}
            aria-label='View employee'
          >
            <Eye className='h-4 w-4' />
          </Link>
        </Button>
      </div>
    ),
    enableSorting: false,
    enableHiding: false,
  },
]
