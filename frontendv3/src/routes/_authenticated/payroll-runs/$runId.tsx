import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { PayrollRunDetail } from '@/features/payroll-runs/detail'

const searchSchema = z.object({})

export const Route = createFileRoute('/_authenticated/payroll-runs/$runId')({
  component: PayrollRunDetail,
  validateSearch: searchSchema,
})
