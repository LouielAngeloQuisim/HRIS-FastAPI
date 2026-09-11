import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import DailyTimeRecordsPage from '@/features/daily-time-records'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(50),
})

export const Route = createFileRoute('/_authenticated/daily-time-records/')({
  component: DailyTimeRecordsPage,
  validateSearch: searchSchema,
})
