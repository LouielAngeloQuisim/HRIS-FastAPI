import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import LeaveLedgerPage from './index'

const { useLeaveLedgerMock } = vi.hoisted(() => ({
  useLeaveLedgerMock: vi.fn(),
}))
vi.mock('@/lib/api/leave-ledger', () => ({
  useLeaveLedger: (...args: unknown[]) => useLeaveLedgerMock(...args),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

describe('LeaveLedgerPage', () => {
  it('shows "No ledger entries found" when data is empty', async () => {
    useLeaveLedgerMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<LeaveLedgerPage />)

    await expect
      .element(getByText('No ledger entries found.'))
      .toBeVisible()
  })

  it('shows permission denied message when not authorized', async () => {
    useCanMock.mockReturnValue(false)

    const { getByText } = await render(<LeaveLedgerPage />)
    await expect
      .element(getByText(/You do not have permission to view leave ledger/i))
      .toBeVisible()
  })
})
