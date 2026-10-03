import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import PayrollPage from '@/features/payroll'

const searchSchema = z.object({})

export const Route = createFileRoute('/_authenticated/payroll/')({
  component: PayrollPage,
  validateSearch: searchSchema,
})
