import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import SSSConfigPage from './index'

vi.mock('./components/sss-resource-form', () => ({
  SSSResourceForm: () => null,
}))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

const { useSSSBracketsMock } = vi.hoisted(() => ({
  useSSSBracketsMock: vi.fn(),
}))
vi.mock('@/lib/api/payroll-config', () => ({
  useSSSBrackets: (...args: unknown[]) => useSSSBracketsMock(...args),
  useDeleteSSSBracket: () => ({ mutateAsync: vi.fn() }),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const SAMPLE = {
  data: [
    {
      id: '1',
      msc_min: 5000,
      msc_max: 35000,
      compensation_min: 0,
      compensation_max: null,
      monthly_salary_credit: 35000,
      employer_ss: 10,
      employer_ec: 30,
      employer_mpf: 0,
      employee_ss: 5,
      employee_mpf: 0,
      effective_date: '2024-01-01',
    },
  ],
  count: 1,
}

describe('SSSConfigPage', () => {
  it('renders brackets and count when query succeeds', async () => {
    useSSSBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByRole, getByText } = await render(<SSSConfigPage />)

    await expect
      .element(getByRole('cell', { name: '0', exact: true }))
      .toBeInTheDocument()
    await expect
      .element(getByRole('cell', { name: 'No upper limit', exact: true }))
      .toBeInTheDocument()
    await expect
      .element(getByRole('cell', { name: '₱35,000', exact: true }))
      .toBeInTheDocument()
    await expect.element(getByText('1 bracket records')).toBeInTheDocument()
  })

  it('shows permission denial when canView is false', async () => {
    useSSSBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockImplementation((_m: string, action: string) =>
      action === 'view' ? false : true
    )

    const { getByText } = await render(<SSSConfigPage />)
    await expect
      .element(getByText(/You do not have permission to view SSS config/i))
      .toBeInTheDocument()
  })

  it('shows Add button only when canCreate is true', async () => {
    useSSSBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation(
      (_m: string, action: string) => action === 'add'
    )
    const denied = await render(<SSSConfigPage />)
    await expect
      .element(denied.getByRole('button', { name: /Add SSS Bracket/i }))
      .not.toBeInTheDocument()

    useCanMock.mockReturnValue(true)
    const allowed = await render(<SSSConfigPage />)
    await expect
      .element(allowed.getByRole('button', { name: /Add SSS Bracket/i }))
      .toBeInTheDocument()
  })

  it('shows edit/delete actions gated by canEdit/canDelete', async () => {
    useSSSBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation(
      (_m: string, action: string) =>
        action === 'view' || action === 'edit' || action === 'delete'
    )
    const { getByTestId } = await render(<SSSConfigPage />)
    await expect.element(getByTestId('edit-sss-button-1')).toBeInTheDocument()
    await expect.element(getByTestId('delete-sss-button-1')).toBeInTheDocument()
  })

  it('shows error state with retry when query fails', async () => {
    const refetch = vi.fn()
    useSSSBracketsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })
    useCanMock.mockReturnValue(true)

    const { getByText, getByRole } = await render(<SSSConfigPage />)
    await expect
      .element(getByText(/Failed to load SSS brackets/i))
      .toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })
})
