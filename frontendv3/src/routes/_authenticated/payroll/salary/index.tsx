import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import SalaryPage from '@/features/salary'

const searchSchema = z.object({})

export const Route = createFileRoute('/_authenticated/payroll/salary/')({
  component: SalaryPage,
  validateSearch: searchSchema,
})
