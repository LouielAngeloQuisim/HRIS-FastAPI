import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import LeaveCalendarPage from '@/features/leave-calendar'

const searchSchema = z.object({
  from: z.string().optional(),
  to: z.string().optional(),
})

export const Route = createFileRoute('/_authenticated/leave-calendar/')({
  component: LeaveCalendarPage,
  validateSearch: searchSchema,
})
