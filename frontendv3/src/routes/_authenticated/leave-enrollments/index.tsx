import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import LeaveEnrollmentsPage from '@/features/leave-enrollment'

const searchSchema = z.object({})

export const Route = createFileRoute('/_authenticated/leave-enrollments/')({
  component: LeaveEnrollmentsPage,
  validateSearch: searchSchema,
})
