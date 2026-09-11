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
import { useCreateDtrAdjustment } from '@/lib/api/dtr-adjustments'
import type { DtrAdjustmentCreate } from '@/lib/api/types'

const formSchema = z.object({
  daily_time_record_id: z.string().min(1, 'Daily Time Record ID is required'),
  adjusted_login_date: z.string().min(1, 'Adjusted login date is required'),
  adjusted_logout_date: z.string().min(1, 'Adjusted logout date is required'),
  reason: z.string().optional(),
  adjusted_date: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

interface Props {
  onClose: () => void
  open: boolean
}

export function DtrAdjustmentForm({ onClose, open }: Props) {
  const createMutation = useCreateDtrAdjustment()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      daily_time_record_id: '',
      adjusted_login_date: '',
      adjusted_logout_date: '',
      reason: '',
      adjusted_date: '',
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      await createMutation.mutateAsync(data as unknown as DtrAdjustmentCreate)
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
          <SheetTitle>Submit DTR Adjustment</SheetTitle>
          <SheetDescription>
            Provide the adjusted login/logout times for the DTR record.
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id='dtr-adjustment-form' onSubmit={form.handleSubmit(onSubmit)} className='flex-1 space-y-6 overflow-y-auto px-4'>
            <FormField control={form.control} name='daily_time_record_id' render={({ field }) => (
              <FormItem>
                <FormLabel>Daily Time Record ID</FormLabel>
                <FormControl><Input {...field} value={field.value ?? ''} data-testid="dtr-adjustment-dtr-id-input" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name='adjusted_login_date' render={({ field }) => (
              <FormItem>
                <FormLabel>Adjusted Login Date</FormLabel>
                <FormControl><Input type='datetime-local' {...field} value={field.value ?? ''} data-testid="dtr-adjustment-login-input" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name='adjusted_logout_date' render={({ field }) => (
              <FormItem>
                <FormLabel>Adjusted Logout Date</FormLabel>
                <FormControl><Input type='datetime-local' {...field} value={field.value ?? ''} data-testid="dtr-adjustment-logout-input" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name='adjusted_date' render={({ field }) => (
              <FormItem>
                <FormLabel>Adjusted Date (optional)</FormLabel>
                <FormControl><Input type='date' {...field} value={field.value ?? ''} data-testid="dtr-adjustment-date-input" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name='reason' render={({ field }) => (
              <FormItem>
                <FormLabel>Reason (optional)</FormLabel>
                <FormControl><Textarea {...field} value={field.value ?? ''} data-testid="dtr-adjustment-reason-input" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>
        <SheetFooter>
          <SheetClose asChild>
            <Button type='button' variant='outline'>Cancel</Button>
          </SheetClose>
          <Button type='submit' form='dtr-adjustment-form' disabled={loading} data-testid="dtr-adjustment-submit-button">
            {loading ? 'Submitting...' : 'Submit Adjustment'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
