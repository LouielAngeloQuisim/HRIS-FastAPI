import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { EmployeesTable } from './employees-table'
import { type Employee } from '../data/schema'

const sample: Employee[] = [
  {
    id: '1',
    employee_code: 'E001',
    first_name: 'Jane',
    middle_name: 'D',
    last_name: 'Doe',
    extension: null,
    birthdate: '1990-01-01',
    birth_place: 'City',
    gender: 'Female',
    civil_status: 'Single',
    email: 'j@b.com',
    zip_code: '1000',
    area: 'North',
    present_barangay: 'Bgy 1',
    present_city: 'City',
    same_address: true,
    permanent_barangay: 'Bgy 1',
    permanent_city: 'City',
    date_hired: '2020-01-01',
    employee_status: 'Active',
    employment_type: 'Regular',
    contract_expiry_date: null,
    date_separated: null,
    probationary_date: null,
    regularization_date: '2020-07-01',
    telephone: '123',
    cellphone: '456',
    profile_photo_path: null,
    position_id: null,
    division_id: null,
    department_id: null,
    user_id: null,
    is_deleted: false,
    created_at: '2020-01-01T00:00:00Z',
    updated_at: '2020-01-01T00:00:00Z',
  },
  {
    id: '2',
    employee_code: 'E002',
    first_name: 'John',
    middle_name: null,
    last_name: 'Smith',
    extension: null,
    birthdate: '1985-06-15',
    birth_place: 'Town',
    gender: 'Male',
    civil_status: 'Married',
    email: 'j@smith.com',
    zip_code: '2000',
    area: 'South',
    present_barangay: 'Bgy 2',
    present_city: 'Town',
    same_address: false,
    permanent_barangay: 'Bgy 3',
    permanent_city: 'Town',
    date_hired: '2019-03-01',
    employee_status: 'Resigned',
    employment_type: 'Contract',
    contract_expiry_date: '2024-03-01',
    date_separated: '2024-02-01',
    probationary_date: null,
    regularization_date: null,
    telephone: null,
    cellphone: '789',
    profile_photo_path: null,
    position_id: null,
    division_id: null,
    department_id: null,
    user_id: null,
    is_deleted: false,
    created_at: '2019-03-01T00:00:00Z',
    updated_at: '2024-02-01T00:00:00Z',
  },
]

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    Link: ({
      children,
      to,
      className,
      ...rest
    }: {
      children?: React.ReactNode
      to: string
      className?: string
    }) => (
      <a href={to} className={className} {...rest}>
        {children}
      </a>
    ),
  }
})

describe('EmployeesTable', () => {
  const search = {}
  const navigate = vi.fn()

  it('renders rows from the data array', async () => {
    const screen = await render(
      <EmployeesTable data={sample} count={2} search={search} navigate={navigate} />
    )

    await expect.element(screen.getByText('E001')).toBeInTheDocument()
    await expect.element(screen.getByText('E002')).toBeInTheDocument()
    await expect.element(screen.getByText('Doe, Jane, D')).toBeInTheDocument()
    await expect.element(screen.getByText('Smith, John')).toBeInTheDocument()
  })

  it('shows empty state when no data', async () => {
    const screen = await render(
      <EmployeesTable data={[]} count={0} search={search} navigate={navigate} />
    )
    await expect.element(screen.getByText('No employees found.')).toBeInTheDocument()
  })
})
