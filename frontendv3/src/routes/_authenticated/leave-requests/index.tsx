import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import LeaveRequestsPage from '@/features/leave-requests'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(50),
  status: z.string().optional(),
})

export const Route = createFileRoute('/_authenticated/leave-requests/')({
  component: LeaveRequestsPage,
  validateSearch: searchSchema,
})
