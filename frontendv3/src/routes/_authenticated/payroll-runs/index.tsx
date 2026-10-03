import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import PayrollRunsPage from '@/features/payroll-runs'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/payroll-runs/')({
  component: PayrollRunsPage,
  validateSearch: searchSchema,
})
