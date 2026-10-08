import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import {
  type EmployeeLatestPayroll,
  type EmployeeRecordsPublic,
} from '@/lib/api/types'
import { EmployeeProfile } from './index'

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

type TaxBenefitMock = {
  id: string
  employee_id: string
  tax_year: number
  paid_on: string
  benefit_type: 'thirteenth_month' | 'other_benefit' | 'de_minimis'
  de_minimis_category?: string | null
  eligibility_evidence?: string[]
  gross_amount: string
  source_reference: string
  correction_of_id: string | null
  correction_reason: string | null
  created_by: string | null
  created_at: string | null
}

const { saveTaxInputs, saveBenefit, salaryQuery, benefitsQuery } = vi.hoisted(() => ({
  saveTaxInputs: vi.fn(),
  saveBenefit: vi.fn(),
  salaryQuery: vi.fn(() => ({
    data: { data: [], count: 0 },
    isPending: false,
    isError: false,
  })),
  benefitsQuery: vi.fn(() => ({
    data: [] as TaxBenefitMock[],
    isPending: false,
    isError: false,
    isSuccess: true,
  })),
}))

vi.mock('@/lib/api/employees', () => ({
  useEmployee: vi.fn(),
  fetchEmployee: vi.fn(),
}))

vi.mock('@/lib/api/payroll', () => ({
  useEmployeeSalaries: () => salaryQuery(),
  useEmployeePayGroupAssignments: () => ({
    data: [],
    isPending: false,
    isError: false,
  }),
  useEmployeeLatestPayroll: vi.fn(() => ({
    data: null,
    isPending: false,
    isError: false,
  })),
  useEmployeeTaxYearDeclaration: () => ({
    data: null,
    isPending: false,
    isError: false,
  }),
  useSaveEmployeeTaxYearDeclaration: () => ({
    mutate: saveTaxInputs,
    isPending: false,
    isError: false,
    isSuccess: false,
  }),
  useEmployeeTaxYearBenefits: () => benefitsQuery(),
  useRecordEmployeeTaxYearBenefit: () => ({
    mutate: saveBenefit,
    isPending: false,
    isError: false,
  }),
}))

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))

vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ employeeId: 'emp-1' }),
  Link: ({
    children,
    to,
    ...rest
  }: {
    children?: React.ReactNode
    to: string
  }) => (
    <a href={to} {...rest}>
      {children}
    </a>
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
    salaryQuery.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
    })
    benefitsQuery.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      isSuccess: true,
    })
  })

  it('renders employee name, code and fields', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    const mockResult = {
      data: mockEmployee,
      isPending: false,
      isError: false,
    }
    vi.mocked(useEmployee).mockReturnValue(
      mockResult as ReturnType<typeof useEmployee>
    )

    const screen = await render(<EmployeeProfile />)

    await expect.element(screen.getByText('Doe, Jane, D')).toBeInTheDocument()
    await expect.element(screen.getByText(/^Female$/)).toBeInTheDocument()
    await expect.element(screen.getByText(/^Regular$/)).toBeInTheDocument()
    await expect
      .element(screen.getByText(/Government IDs/i))
      .toBeInTheDocument()
  })

  it('lets an authorized payroll approver enter and verify annual tax opening figures', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    const screen = await render(<EmployeeProfile />)

    await expect
      .element(screen.getByText(/BIR tax-year inputs/i))
      .toBeInTheDocument()
    await userEvent.fill(
      screen.getByLabelText(/Opening balances are complete through/i),
      '2026-09-30'
    )
    await userEvent.fill(
      screen.getByLabelText(/Taxable compensation already paid this year/i),
      '125000.00'
    )
    await userEvent.fill(
      screen.getByLabelText(/Withholding tax already withheld this year/i),
      '4500.00'
    )
    await userEvent.fill(
      screen.getByLabelText(/Opening payroll periods covered/i),
      '6'
    )
    await userEvent.fill(
      screen.getByLabelText(/Source \/ review note/i),
      'Form 2316 reviewed'
    )
    await userEvent.click(
      screen.getByLabelText(/I reconciled 13th-month and other benefit payments/i)
    )
    await userEvent.click(screen.getByLabelText(/I reviewed these figures/i))
    await userEvent.click(
      screen.getByRole('button', { name: /Save tax-year inputs/i })
    )

    expect(saveTaxInputs).toHaveBeenCalledWith(
      expect.objectContaining({
        tax_classification: 'ordinary',
        opening_as_of: '2026-09-30',
        taxable_compensation_ytd: '125000.00',
        tax_withheld_ytd: '4500.00',
        opening_pay_period_count: 6,
        opening_pay_period_type: 'monthly',
        previous_employer_included: false,
        opening_benefits_exempt_ytd: '0.00',
        opening_benefits_reconciled: true,
        opening_de_minimis_annual_ytd: {
          uniform_clothing: '0.00',
          actual_medical_assistance: '0.00',
          achievement_award: '0.00',
          christmas_anniversary_gift: '0.00',
          cba_productivity_incentive: '0.00',
        },
        opening_de_minimis_monthly_ytd: {
          medical_cash_dependents: '0.00',
          rice_subsidy: '0.00',
          laundry_allowance: '0.00',
        },
        is_verified: true,
      })
    )
  })

  it('records a paid 13th-month benefit with its source reference', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    const screen = await render(<EmployeeProfile />)
    await userEvent.fill(screen.getByLabelText('Paid date'), '2026-12-15')
    await userEvent.fill(screen.getByLabelText('Gross amount paid'), '30000.00')
    await userEvent.fill(screen.getByLabelText('Payment source reference'), 'Voucher PV-26-12')
    await userEvent.click(screen.getByRole('button', { name: 'Record paid benefit' }))
    expect(saveBenefit).toHaveBeenCalledWith(
      expect.objectContaining({
        paid_on: '2026-12-15',
        benefit_type: 'thirteenth_month',
        gross_amount: '30000.00',
        source_reference: 'Voucher PV-26-12',
        correction_of_id: null,
        correction_reason: null,
      }),
      expect.any(Object)
    )
  })

  it('requires and records evidence for conditional de minimis benefits', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    const screen = await render(<EmployeeProfile />)
    await userEvent.selectOptions(screen.getByLabelText('Benefit type'), 'de_minimis')
    await userEvent.selectOptions(screen.getByLabelText('De minimis category'), 'actual_medical_assistance')
    await userEvent.fill(screen.getByLabelText('Paid date'), '2026-07-01')
    await userEvent.fill(screen.getByLabelText('Gross amount paid'), '12000.00')
    await userEvent.fill(screen.getByLabelText('Payment source reference'), 'Voucher PV-26-071')
    const submit = screen.getByRole('button', { name: 'Record paid benefit' })
    expect(submit).toBeDisabled()
    await userEvent.click(screen.getByLabelText('Actual medical expense documentation verified'))
    expect(submit).toBeEnabled()
    await userEvent.click(submit)
    expect(saveBenefit).toHaveBeenCalledWith(
      expect.objectContaining({
        benefit_type: 'de_minimis',
        de_minimis_category: 'actual_medical_assistance',
        eligibility_evidence: ['actual_medical_documentation'],
      }),
      expect.any(Object)
    )
  })

  it('records a reasoned full reversal for a paid benefit', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    benefitsQuery.mockReturnValue({
      data: [
        {
          id: 'benefit-1',
          employee_id: 'emp-1',
          tax_year: 2026,
          paid_on: '2026-12-15',
          benefit_type: 'thirteenth_month',
          gross_amount: '30000.00',
          source_reference: 'Voucher PV-26-12',
          correction_of_id: null,
          correction_reason: null,
          created_by: 'user-1',
          created_at: '2026-12-15T00:00:00Z',
        },
      ],
      isPending: false,
      isError: false,
      isSuccess: true,
    })
    const screen = await render(<EmployeeProfile />)
    await userEvent.click(screen.getByRole('button', { name: 'Reverse record' }))
    await userEvent.fill(screen.getByLabelText('Paid date'), '2026-12-16')
    await userEvent.fill(screen.getByLabelText('Payment source reference'), 'Correction CM-12-16')
    await userEvent.fill(screen.getByLabelText('Reason for full reversal'), 'Duplicate payment entry')
    await userEvent.click(screen.getByRole('button', { name: 'Record full reversal' }))
    expect(saveBenefit).toHaveBeenCalledWith(
      expect.objectContaining({
        paid_on: '2026-12-16',
        benefit_type: 'thirteenth_month',
        gross_amount: '-30000.00',
        source_reference: 'Correction CM-12-16',
        correction_of_id: 'benefit-1',
        correction_reason: 'Duplicate payment entry',
      }),
      expect.any(Object)
    )
  })

  it('requires wage-order evidence before verifying minimum-wage-earner treatment', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    const screen = await render(<EmployeeProfile />)

    await userEvent.selectOptions(
      screen.getByLabelText('Tax classification'),
      'minimum_wage_earner'
    )
    await userEvent.fill(
      screen.getByLabelText(/Opening balances are complete through/i),
      '2026-06-30'
    )
    await expect
      .element(screen.getByText(/assigned work location/i))
      .toBeInTheDocument()
    const saveButton = screen.getByRole('button', {
      name: /Save tax-year inputs/i,
    })
    await expect.element(saveButton).toBeDisabled()

    await userEvent.fill(
      screen.getByLabelText(/Source \/ review note/i),
      'DOLE Wage Order evidence; assigned workplace confirmed'
    )
    await expect.element(saveButton).not.toBeDisabled()
    await userEvent.click(saveButton)
    expect(saveTaxInputs).toHaveBeenCalledWith(
      expect.objectContaining({
        tax_classification: 'minimum_wage_earner',
        source_reference:
          'DOLE Wage Order evidence; assigned workplace confirmed',
      })
    )
  })

  it('shows the latest finalized employee deductions separately from employer contributions', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    const { useEmployeeLatestPayroll } = await import('@/lib/api/payroll')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    vi.mocked(useEmployeeLatestPayroll).mockReturnValue({
      data: {
        run_id: 'run-1',
        employee_id: 'emp-1',
        employee_name: 'Jane Doe',
        cutoff_type: 'semi_monthly',
        date_from: '2026-10-16',
        date_to: '2026-10-31',
        basic_rate: '26000.00',
        rate_date_from: '2026-10-01',
        rate_date_to: '2026-10-31',
        earnings: { regular: '13000.00' },
        deductions: {
          attendance: '0.00',
          bir_withholding: '850.00',
          statutory: {
            sss: '1300.00',
            philhealth: '325.00',
            pagibig: '100.00',
          },
          employer_contributions: {
            sss: '2200.00',
            philhealth: '325.00',
            pagibig: '200.00',
          },
        },
        gross_pay: '13000.00',
        total_deductions: '2575.00',
        net_pay: '10425.00',
        overtime_pay: '0.00',
        thirteenth_month: '0.00',
        non_taxable_income: '0.00',
        taxable_income: '13000.00',
        status: 'approved',
      } satisfies EmployeeLatestPayroll,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useEmployeeLatestPayroll>)

    const screen = await render(<EmployeeProfile />)

    await expect
      .element(screen.getByRole('region', { name: 'Latest finalized payroll' }))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('Period 2026-10-16 to 2026-10-31'))
      .toBeInTheDocument()
    await expect
      .element(
        screen.getByText(
          /Employer contributions \(not deducted from net pay\)/i
        )
      )
      .toBeInTheDocument()
    await expect.element(screen.getByText('₱1,300.00')).toBeInTheDocument()
    await expect.element(screen.getByText('₱2,200.00')).toBeInTheDocument()
  })

  it('shows effective-dated salary history and chooses the active rate for the summary', async () => {
    const { useEmployee } = await import('@/lib/api/employees')
    vi.mocked(useEmployee).mockReturnValue({
      data: mockEmployee,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useEmployee>)
    salaryQuery.mockReturnValue({
      data: {
        count: 2,
        data: [
          {
            id: 'salary-new',
            employee_id: 'emp-1',
            effective_date: '2026-07-01',
            basic_rate: '30000.00',
            currency: 'PHP',
            pay_type: 'monthly',
            is_active: true,
            is_deleted: false,
            created_at: null,
            updated_at: null,
          },
          {
            id: 'salary-old',
            employee_id: 'emp-1',
            effective_date: '2025-01-01',
            basic_rate: '26000.00',
            currency: 'PHP',
            pay_type: 'monthly',
            is_active: false,
            is_deleted: false,
            created_at: null,
            updated_at: null,
          },
        ],
      },
      isPending: false,
      isError: false,
    } as ReturnType<typeof salaryQuery>)

    const screen = await render(<EmployeeProfile />)

    await expect
      .element(screen.getByRole('list').getByText('PHP 30000.00'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/2026-07-01 · monthly · active/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/2025-01-01 · monthly · inactive/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('list').getByText('PHP 26000.00'))
      .toBeInTheDocument()
  })
})
