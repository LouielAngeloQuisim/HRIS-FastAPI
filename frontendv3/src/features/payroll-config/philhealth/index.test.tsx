import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import PhilHealthConfigPage from './index'

vi.mock('./components/philhealth-resource-form', () => ({
  PhilHealthResourceForm: () => null,
}))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

const { usePhilHealthBracketsMock } = vi.hoisted(() => ({ usePhilHealthBracketsMock: vi.fn() }))
vi.mock('@/lib/api/payroll-config', () => ({
  usePhilHealthBrackets: (...args: unknown[]) => usePhilHealthBracketsMock(...args),
  useDeletePhilHealthBracket: () => ({ mutateAsync: vi.fn() }),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const SAMPLE = {
  data: [
    {
      id: '1',
      salary_min: 10000,
      salary_max: 100000,
      rate: 5,
      employer_share: 2.5,
      employee_share: 2.5,
      effective_date: '2024-01-01',
    },
  ],
  count: 1,
}

describe('PhilHealthConfigPage', () => {
  it('renders brackets and count when query succeeds', async () => {
    usePhilHealthBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByRole, getByText } = await render(<PhilHealthConfigPage />)

    await expect.element(getByRole('cell', { name: '10,000', exact: true })).toBeInTheDocument()
    await expect.element(getByRole('cell', { name: '100,000', exact: true })).toBeInTheDocument()
    await expect.element(getByText('1 bracket records')).toBeInTheDocument()
  })

  it('shows permission denial when canView is false', async () => {
    usePhilHealthBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockImplementation((_m: string, action: string) => action === 'view' ? false : true)

    const { getByText } = await render(<PhilHealthConfigPage />)
    await expect.element(getByText(/You do not have permission to view PhilHealth config/i)).toBeInTheDocument()
  })

  it('shows Add button only when canCreate is true', async () => {
    usePhilHealthBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation((_m: string, action: string) => action === 'add')
    const denied = await render(<PhilHealthConfigPage />)
    await expect.element(denied.getByRole('button', { name: /Add PhilHealth Bracket/i })).not.toBeInTheDocument()

    useCanMock.mockReturnValue(true)
    const allowed = await render(<PhilHealthConfigPage />)
    await expect.element(allowed.getByRole('button', { name: /Add PhilHealth Bracket/i })).toBeInTheDocument()
  })

  it('offers authorized edit and deactivation operations', async () => {
    usePhilHealthBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation((_m: string, action: string) => action === 'view' || action === 'edit' || action === 'delete')
    const { getByTestId } = await render(<PhilHealthConfigPage />)
    await expect.element(getByTestId('edit-philhealth-button-1')).toBeInTheDocument()
    await expect.element(getByTestId('delete-philhealth-button-1')).toBeInTheDocument()
  })

  it('shows error state with retry when query fails', async () => {
    const refetch = vi.fn()
    usePhilHealthBracketsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })
    useCanMock.mockReturnValue(true)

    const { getByText, getByRole } = await render(<PhilHealthConfigPage />)
    await expect.element(getByText(/Failed to load PhilHealth brackets/i)).toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })
  it('hides configuration mutations from a view-only caller', async () => {
    usePhilHealthBracketsMock.mockReturnValue({ data: SAMPLE, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockImplementation((_module: string, action: string) => action === 'view')
    const screen = await render(<PhilHealthConfigPage />)
    await expect.element(screen.getByTestId('edit-philhealth-button-1')).not.toBeInTheDocument()
    await expect.element(screen.getByTestId('delete-philhealth-button-1')).not.toBeInTheDocument()
  })

})
