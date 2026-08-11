import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render } from 'vitest-browser-react'
import { EmployeeProfile } from './index'
import { type EmployeeRecordsPublic } from '@/lib/api/types'

const mockEmployee: EmployeeRecordsPublic = {
  id: 'emp-1',
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
}

vi.mock('@/lib/api/employees', () => ({
  useEmployee: vi.fn(),
  fetchEmployee: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ employeeId: 'emp-1' }),
  Link: ({ children, to, ...rest }: { children?: React.ReactNode; to: string }) => (
    <a href={to} {...rest}>{children}</a>
  ),
  useNavigate: () => vi.fn(),
  Outlet: () => null,
  createRoute: () => ({}),
  createRootRoute: () => ({}),
  createRouter: () => ({}),
  RouterProvider: ({ children }: { children: React.ReactNode }) => children,
  useRouterState: () => ({}),
  useLocation: () => ({ pathname: '/' }),
}))

describe('EmployeeProfile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders employee name, code and fields', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    const mockResult = {
      data: mockEmployee,
      isPending: false,
      isError: false,
    }
    vi.mocked(useEmployee).mockReturnValue(mockResult as ReturnType<typeof useEmployee>)

    const screen = await render(<EmployeeProfile />)

    await expect.element(screen.getByText('Doe, Jane, D')).toBeInTheDocument()
    await expect.element(screen.getByText(/^Female$/)).toBeInTheDocument()
    await expect.element(screen.getByText(/^Regular$/)).toBeInTheDocument()
    await expect
      .element(screen.getByText(/Government IDs/i))
      .toBeInTheDocument()
  })
})
