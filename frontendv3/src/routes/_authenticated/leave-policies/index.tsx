import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import LeavePoliciesPage from '@/features/leave-policies'

const searchSchema = z.object({})

export const Route = createFileRoute('/_authenticated/leave-policies/')({
  component: LeavePoliciesPage,
  validateSearch: searchSchema,
})
