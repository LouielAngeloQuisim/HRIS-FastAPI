import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useSubmitLeaveRequest } from '@/lib/api/leave-requests'
import type { LeaveRequestCreate } from '@/lib/api/types'

const formSchema = z.object({
  employee_id: z.string().min(1, 'Employee ID is required'),
  policy_id: z.string().min(1, 'Policy ID is required'),
  date_start: z.string().min(1, 'Start date is required'),
  date_end: z.string().min(1, 'End date is required'),
  requested_hours: z.number().optional(),
  reason: z.string().optional(),
  document_ref: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

interface Props {
  onClose: () => void
  open: boolean
}

export function LeaveRequestForm({ onClose, open }: Props) {
  const createMutation = useSubmitLeaveRequest()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      employee_id: '',
      policy_id: '',
      date_start: '',
      date_end: '',
      requested_hours: undefined,
      reason: '',
      document_ref: '',
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      await createMutation.mutateAsync(data as unknown as LeaveRequestCreate)
      onClose()
    } catch (_e) {
      // _e is caught error
    }
  }

  const loading = createMutation.isPending

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className='flex flex-col'>
        <SheetHeader>
          <SheetTitle>Submit Leave Request</SheetTitle>
          <SheetDescription>
            Fill in the leave request details below.
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id='leave-request-form' onSubmit={form.handleSubmit(onSubmit)} className='flex-1 space-y-6 overflow-y-auto px-4'>
              <FormField control={form.control} name='employee_id' render={({ field }) => (
                <FormItem>
                  <FormLabel>Employee ID</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="leave-request-employee-id-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name='policy_id' render={({ field }) => (
                <FormItem>
                  <FormLabel>Policy ID</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="leave-request-policy-id-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name='date_start' render={({ field }) => (
                <FormItem>
                  <FormLabel>Date Start</FormLabel>
                  <FormControl><Input type='date' {...field} value={field.value ?? ''} data-testid="leave-request-date-start-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name='date_end' render={({ field }) => (
                <FormItem>
                  <FormLabel>Date End</FormLabel>
                  <FormControl><Input type='date' {...field} value={field.value ?? ''} data-testid="leave-request-date-end-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name='requested_hours' render={({ field }) => (
                <FormItem>
                  <FormLabel>Requested Hours (optional)</FormLabel>
                  <FormControl><Input type='number' step='0.5' {...field} value={field.value ?? ''} onChange={(e) => field.onChange(e.target.value ? Number(e.target.value) : undefined)} data-testid="leave-request-hours-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name='reason' render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason (optional)</FormLabel>
                  <FormControl><Textarea {...field} value={field.value ?? ''} data-testid="leave-request-reason-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name='document_ref' render={({ field }) => (
                <FormItem>
                  <FormLabel>Document Reference (optional)</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="leave-request-document-ref-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
          </form>
        </Form>
        <SheetFooter>
          <SheetClose asChild>
            <Button type='button' variant='outline'>Cancel</Button>
          </SheetClose>
          <Button type='submit' form='leave-request-form' disabled={loading} data-testid="leave-request-submit-button">
            {loading ? 'Submitting...' : 'Submit Request'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
