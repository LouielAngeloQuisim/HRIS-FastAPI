import { createFileRoute } from '@tanstack/react-router'
import PayrollSettingsPage from '@/features/payroll-settings'

export const Route = createFileRoute('/_authenticated/payroll-settings')({
  component: PayrollSettingsPage,
})
