import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import PagIBIGConfigPage from './index'

vi.mock('./components/pagibig-resource-form', () => ({
  PagIBIGResourceForm: () => null,
}))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

const { usePagIBIGBracketsMock } = vi.hoisted(() => ({ usePagIBIGBracketsMock: vi.fn() }))
vi.mock('@/lib/api/payroll-config', () => ({
  usePagIBIGBrackets: (...args: unknown[]) => usePagIBIGBracketsMock(...args),
  useDeletePagIBIGBracket: () => ({ mutateAsync: vi.fn() }),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const SAMPLE = {
  data: [
    {
      id: '1',
      salary_min: 5000,
      salary_max: 10000,
      employee_rate: 1,
      employer_rate: 2,
      effective_date: '2024-01-01',
    },
  ],
  count: 1,
}

describe('PagIBIGConfigPage', () => {
  it('renders brackets and count when query succeeds', async () => {
    usePagIBIGBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByRole, getByText } = await render(<PagIBIGConfigPage />)

    await expect.element(getByRole('cell', { name: '5,000', exact: true })).toBeInTheDocument()
    await expect.element(getByRole('cell', { name: '10,000', exact: true })).toBeInTheDocument()
    await expect.element(getByText('1 bracket records')).toBeInTheDocument()
  })

  it('shows permission denial when canView is false', async () => {
    usePagIBIGBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockImplementation((_m: string, action: string) => action === 'view' ? false : true)

    const { getByText } = await render(<PagIBIGConfigPage />)
    await expect.element(getByText(/You do not have permission to view Pag-IBIG config/i)).toBeInTheDocument()
  })

  it('shows Add button only when canCreate is true', async () => {
    usePagIBIGBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation((_m: string, action: string) => action === 'add')
    const denied = await render(<PagIBIGConfigPage />)
    await expect.element(denied.getByRole('button', { name: /Add Pag-IBIG Bracket/i })).not.toBeInTheDocument()

    useCanMock.mockReturnValue(true)
    const allowed = await render(<PagIBIGConfigPage />)
    await expect.element(allowed.getByRole('button', { name: /Add Pag-IBIG Bracket/i })).toBeInTheDocument()
  })

  it('does not offer edit/delete operations absent from the current backend', async () => {
    usePagIBIGBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation((_m: string, action: string) => action === 'view' || action === 'edit' || action === 'delete')
    const { getByTestId } = await render(<PagIBIGConfigPage />)
    await expect.element(getByTestId('edit-pagibig-button-1')).not.toBeInTheDocument()
    await expect.element(getByTestId('delete-pagibig-button-1')).not.toBeInTheDocument()
  })

  it('shows error state with retry when query fails', async () => {
    const refetch = vi.fn()
    usePagIBIGBracketsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })
    useCanMock.mockReturnValue(true)

    const { getByText, getByRole } = await render(<PagIBIGConfigPage />)
    await expect.element(getByText(/Failed to load Pag-IBIG brackets/i)).toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })
})
