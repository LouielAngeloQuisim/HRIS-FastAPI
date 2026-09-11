import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import LeaveLedgerPage from '@/features/leave-ledger'

const searchSchema = z.object({
  year: z.number().optional().catch(new Date().getFullYear()),
})

export const Route = createFileRoute('/_authenticated/leave-ledger/')({
  component: LeaveLedgerPage,
  validateSearch: searchSchema,
})
