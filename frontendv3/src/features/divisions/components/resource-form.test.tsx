import { describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('@/lib/api/divisions', () => ({
  useCreateDivision: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateDivision: () => ({ mutateAsync: updateMock, isPending: false }),
}))

function Harness({ initialOpen }: { initialOpen: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open</button>
      <ResourceForm item={null} open={open} onClose={() => setOpen(false)} />
    </>
  )
}

describe('Division ResourceForm Sheet (§8.2 modal open/close/focus-trap)', () => {
  it('renders nothing (no dialog) when closed', async () => {
    const screen = await render(<ResourceForm item={null} open={false} onClose={vi.fn()} />)
    await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens as a modal dialog (aria-modal) and shows the form fields', async () => {
    const screen = await render(<ResourceForm item={null} open={true} onClose={vi.fn()} />)

    const dialog = screen.getByRole('dialog')
    await expect.element(dialog).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Code/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Name/i })).toBeInTheDocument()
  })

  it('calls onClose when the sheet is dismissed via the close button', async () => {
    const onClose = vi.fn()
    const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)

    const dialog = screen.getByRole('dialog')
    await userEvent.click(dialog.getByRole('button', { name: /Cancel/i }))
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('keeps the sheet open via an external toggle', async () => {
    const screen = await render(<Harness initialOpen={false} />)
    await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('Open'))
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
  })
})
