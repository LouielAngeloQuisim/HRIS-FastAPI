import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import BIRConfigPage from './index'

vi.mock('./components/bir-resource-form', () => ({
  BIRResourceForm: () => null,
}))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

const { useBIRBracketsMock } = vi.hoisted(() => ({ useBIRBracketsMock: vi.fn() }))
vi.mock('@/lib/api/payroll-config', () => ({
  useBIRBrackets: (...args: unknown[]) => useBIRBracketsMock(...args),
  useDeleteBIRBracket: () => ({ mutateAsync: vi.fn() }),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const SAMPLE = {
  data: [
    {
      id: '1',
      period: 'monthly',
      bracket_min: 0,
      bracket_max: 20833,
      base_tax: 0,
      excess_rate: 20,
      effective_date: '2024-01-01',
      source_reference: null,
    },
  ],
  count: 1,
}

describe('BIRConfigPage', () => {
  it('renders brackets and count when query succeeds', async () => {
    useBIRBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByRole, getByText } = await render(<BIRConfigPage />)

    await expect.element(getByRole('cell', { name: '20,833', exact: true })).toBeInTheDocument()
    await expect.element(getByRole('cell', { name: '20%' })).toBeInTheDocument()
    await expect.element(getByText('1 bracket records')).toBeInTheDocument()
  })

  it('labels rows without provenance as unverified legacy values', async () => {
    useBIRBracketsMock.mockReturnValue({ data: SAMPLE, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)
    const { getByText } = await render(<BIRConfigPage />)
    await expect.element(getByText('No source recorded')).toBeInTheDocument()
  })

  it('shows secure source references as links', async () => {
    useBIRBracketsMock.mockReturnValue({
      data: { ...SAMPLE, data: [{ ...SAMPLE.data[0], source_reference: 'https://bir.gov.ph/table.pdf' }] },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)
    const { getByRole } = await render(<BIRConfigPage />)
    await expect.element(getByRole('link', { name: 'View source' })).toHaveAttribute('href', 'https://bir.gov.ph/table.pdf')
  })

  it('shows permission denial when canView is false', async () => {
    useBIRBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockImplementation((_m: string, action: string) => action === 'view' ? false : true)

    const { getByText } = await render(<BIRConfigPage />)
    await expect.element(getByText(/You do not have permission to view BIR config/i)).toBeInTheDocument()
  })

  it('shows Add button only when canCreate is true', async () => {
    useBIRBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation((_m: string, action: string) => action === 'add')
    const denied = await render(<BIRConfigPage />)
    await expect.element(denied.getByRole('button', { name: /Add BIR Bracket/i })).not.toBeInTheDocument()

    useCanMock.mockReturnValue(true)
    const allowed = await render(<BIRConfigPage />)
    await expect.element(allowed.getByRole('button', { name: /Add BIR Bracket/i })).toBeInTheDocument()
  })

  it('offers authorized edit and deactivation operations', async () => {
    useBIRBracketsMock.mockReturnValue({
      data: SAMPLE,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    useCanMock.mockImplementation((_m: string, action: string) => action === 'view' || action === 'edit' || action === 'delete')
    const { getByTestId } = await render(<BIRConfigPage />)
    await expect.element(getByTestId('edit-bir-button-1')).toBeInTheDocument()
    await expect.element(getByTestId('delete-bir-button-1')).toBeInTheDocument()
  })

  it('shows error state with retry when query fails', async () => {
    const refetch = vi.fn()
    useBIRBracketsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })
    useCanMock.mockReturnValue(true)

    const { getByText, getByRole } = await render(<BIRConfigPage />)
    await expect.element(getByText(/Failed to load BIR brackets/i)).toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })
  it('hides configuration mutations from a view-only caller', async () => {
    useBIRBracketsMock.mockReturnValue({ data: SAMPLE, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockImplementation((_module: string, action: string) => action === 'view')
    const screen = await render(<BIRConfigPage />)
    await expect.element(screen.getByTestId('edit-bir-button-1')).not.toBeInTheDocument()
    await expect.element(screen.getByTestId('delete-bir-button-1')).not.toBeInTheDocument()
  })

})
