import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import DivisionPage from './index'

// Isolate the list page from its child dialogs/drawers.
vi.mock('./components/resource-form', () => ({ ResourceForm: () => null }))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

const { useDivisionsMock } = vi.hoisted(() => ({ useDivisionsMock: vi.fn() }))
vi.mock('@/lib/api/divisions', () => ({
  useDivisions: (...args: unknown[]) => useDivisionsMock(...args),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const DIVISIONS = {
  data: [
    { id: 'd1', code: 'D-01', name: 'North', description: 'desc', director_id: 'u1' },
    { id: 'd2', code: 'D-02', name: 'South', description: 'desc', director_id: 'u2' },
  ],
  count: 2,
}

describe('Divisions list (§8.1 / §8.6)', () => {
  it('renders rows bound to useDivisions data and the count', async () => {
    useDivisionsMock.mockReturnValue({
      data: DIVISIONS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<DivisionPage />)

    await expect.element(getByText('D-01')).toBeInTheDocument()
    await expect.element(getByText('North')).toBeInTheDocument()
    await expect.element(getByText('D-02')).toBeInTheDocument()
    await expect.element(getByText('South')).toBeInTheDocument()
    // page-size = 20, count shows total records
    await expect.element(getByText('2 records')).toBeInTheDocument()
  })

  it('shows the Add button only when canCreate (permission gate)', async () => {
    useDivisionsMock.mockReturnValue({
      data: DIVISIONS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    // Denied
    useCanMock.mockImplementation((_m: string, action: string) =>
      action === 'view'
    )
    const denied = await render(<DivisionPage />)
    await expect
      .element(denied.getByRole('button', { name: /Add Division/i }))
      .not.toBeInTheDocument()

    // Allowed
    useCanMock.mockReturnValue(true)
    const allowed = await render(<DivisionPage />)
    await expect
      .element(allowed.getByRole('button', { name: /Add Division/i }))
      .toBeInTheDocument()
  })

  it('renders the error state with a retry control when the query fails', async () => {
    const refetch = vi.fn()
    useDivisionsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })
    useCanMock.mockReturnValue(true)

    const { getByText, getByRole } = await render(<DivisionPage />)
    await expect
      .element(getByText(/Failed to load divisions/i))
      .toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })
})
