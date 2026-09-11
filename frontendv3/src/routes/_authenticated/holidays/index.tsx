import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import HolidaysPage from '@/features/holidays'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(50),
})

export const Route = createFileRoute('/_authenticated/holidays/')({
  component: HolidaysPage,
  validateSearch: searchSchema,
})
