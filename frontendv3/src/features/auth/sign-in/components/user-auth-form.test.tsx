import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, type RenderResult } from 'vitest-browser-react'
import { type Locator, userEvent } from 'vitest/browser'
import { UserAuthForm } from './user-auth-form'

const FORM_MESSAGES = {
  emailEmpty: 'Please enter your email.',
  passwordEmpty: 'Please enter your password.',
  passwordShort: 'Password must be at least 7 characters long.',
} as const

const navigate = vi.fn()
const setUserMock = vi.fn()
const setPermissionsMock = vi.fn()
const setAccessTokenMock = vi.fn()

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: () => ({
    auth: {
      setUser: setUserMock,
      setPermissions: setPermissionsMock,
      setAccessToken: setAccessTokenMock,
    },
  }),
  toAuthUser: (user: { id: string; email: string }) => ({
    id: user.id,
    email: user.email,
    fullName: null,
    isSuperuser: false,
    roleId: null,
    roleCode: null,
  }),
}))

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => navigate,
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

const loginMutate = vi.fn()
vi.mock('@/lib/api/auth', () => ({
  useLogin: () => ({ mutateAsync: loginMutate }),
  fetchMe: vi.fn(async () => ({
    id: 'u1',
    email: 'a@b.com',
    is_active: true,
    is_superuser: false,
    full_name: 'A B',
    role_id: 'r1',
    created_at: null,
  })),
  fetchPermissions: vi.fn(async () => ({
    role_code: 'SADM',
    is_superuser: false,
    permissions: {},
  })),
}))

describe('UserAuthForm', () => {
  describe('Rendering without redirectTo', () => {
    let screen: RenderResult
    let emailInput: Locator
    let passwordInput: Locator
    let signInButton: Locator
    let forgotPasswordLink: Locator

    beforeEach(async () => {
      vi.clearAllMocks()
      screen = await render(<UserAuthForm />)
      emailInput = screen.getByRole('textbox', { name: /^UserName \/ Email ID$/i })
      passwordInput = screen.getByLabelText(/^Password$/i)
      signInButton = screen.getByRole('button', { name: /^Sign In$/i })
      forgotPasswordLink = screen.getByText(/^Forgot password\?$/i)
    })

    it('renders fields, submit button, and forgot password link', async () => {
      await expect.element(emailInput).toBeInTheDocument()
      await expect.element(passwordInput).toBeInTheDocument()
      await expect.element(signInButton).toBeInTheDocument()
      await expect.element(forgotPasswordLink).toBeInTheDocument()
    })

    it('shows validation messages when submitting empty form', async () => {
      await userEvent.click(signInButton)

      await expect
        .element(screen.getByText(FORM_MESSAGES.emailEmpty))
        .toBeInTheDocument()
      await expect
        .element(screen.getByText(FORM_MESSAGES.passwordEmpty))
        .toBeInTheDocument()
    })

    it('authenticates and navigates to default route on success', async () => {
      loginMutate.mockResolvedValueOnce({
        access_token: 'at',
        refresh_token: 'rt',
        token_type: 'bearer',
        expires_in: 1800,
      })

      await userEvent.fill(emailInput, 'a@b.com')
      await userEvent.fill(passwordInput, '1234567')

      await userEvent.click(signInButton)

      await vi.waitFor(() => expect(loginMutate).toHaveBeenCalledOnce())
      expect(loginMutate).toHaveBeenCalledWith({
        email: 'a@b.com',
        password: '1234567',
      })
      expect(setUserMock).toHaveBeenCalledOnce()
      expect(setPermissionsMock).toHaveBeenCalledOnce()
      expect(setAccessTokenMock).toHaveBeenCalledWith('at')

      await vi.waitFor(() =>
        expect(navigate).toHaveBeenCalledWith({ to: '/', replace: true })
      )
    })

    it('shows an error toast and does not navigate on wrong credentials', async () => {
      loginMutate.mockRejectedValueOnce({ response: { status: 400 } })

      await userEvent.fill(emailInput, 'a@b.com')
      await userEvent.fill(passwordInput, '1234567')

      await userEvent.click(signInButton)

      await vi.waitFor(() => expect(loginMutate).toHaveBeenCalledOnce())
      await vi.waitFor(() => expect(navigate).not.toHaveBeenCalled())
    })
  })

  it('navigates to redirectTo when provided', async () => {
    vi.clearAllMocks()
    loginMutate.mockResolvedValueOnce({
      access_token: 'at',
      refresh_token: 'rt',
      token_type: 'bearer',
      expires_in: 1800,
    })

    const { getByRole, getByLabelText } = await render(
      <UserAuthForm redirectTo='/settings' />
    )

    await userEvent.fill(getByRole('textbox', { name: /Email/i }), 'a@b.com')
    await userEvent.fill(getByLabelText('Password'), '1234567')

    await userEvent.click(getByRole('button', { name: /Sign in/i }))

    await vi.waitFor(() => expect(loginMutate).toHaveBeenCalledOnce())
    expect(setAccessTokenMock).toHaveBeenCalledOnce()

    await vi.waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: '/settings',
        replace: true,
      })
    )
  })
})
