import { saveErrorMessage } from '@/lib/api/save-error'
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
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useCreateBIRBracket, useUpdateBIRBracket } from '@/lib/api/payroll-config'
import type { BIRBracketPublic } from '@/lib/api/types'

const formSchema = z.object({
  period: z.enum(['daily', 'weekly', 'semi_monthly', 'monthly']),
  bracket_min: z.coerce.number<number>().min(0),
  bracket_max: z.coerce.number<number>().min(0).nullable(),
  base_tax: z.coerce.number<number>().min(0),
  excess_rate: z.coerce.number<number>().min(0).max(100),
  effective_date: z.string().min(1, 'Select an effective date.'),
})
type FormData = z.infer<typeof formSchema>

interface Props {
  item: BIRBracketPublic | null
  onClose: () => void
  open: boolean
}

export function BIRResourceForm({ item, onClose, open }: Props) {
  const createMutation = useCreateBIRBracket()
  const updateMutation = useUpdateBIRBracket()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: item
      ? {
          period: item.period as FormData['period'],
          bracket_min: Number(item.bracket_min),
          bracket_max: item.bracket_max === null ? null : Number(item.bracket_max),
          base_tax: Number(item.base_tax),
          excess_rate: Number(item.excess_rate),
          effective_date: item.effective_date,
        }
      : {
          period: 'monthly',
          bracket_min: 0,
          bracket_max: null,
          base_tax: 0,
          excess_rate: 0,
          effective_date: '',
        },
  })

  const onSubmit = async (data: FormData) => {
    form.clearErrors('root.server')
    try {
      if (item) {
        await updateMutation.mutateAsync({ id: item.id, data })
      } else {
        await createMutation.mutateAsync(data)
      }
      onClose()
    } catch (error) {
      form.setError('root.server', { message: saveErrorMessage(error) })
    }
  }

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className='w-full overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{item ? 'Edit BIR Bracket' : 'Add BIR Bracket'}</SheetTitle>
          <SheetDescription>
            {item ? 'Update the BIR bracket configuration.' : 'Create a new BIR bracket configuration.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-4 px-4 py-4'>
            {form.formState.errors.root?.server?.message && <p role='alert'>{form.formState.errors.root.server.message}</p>}
            <FormField
              control={form.control}
              name='period'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Period</FormLabel>
                  <FormControl>
                    <select {...field} data-testid="bir-period-input" className='h-9 w-full rounded-md border bg-background px-3'>
                      <option value='daily'>Daily</option>
                      <option value='weekly'>Weekly</option>
                      <option value='semi_monthly'>Semi-monthly</option>
                      <option value='monthly'>Monthly</option>
                    </select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='bracket_min'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Bracket Min (₱)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`bir-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='bracket_max'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Bracket Max (₱, optional)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} value={field.value ?? ''} onChange={(event) => field.onChange(event.target.value === '' ? null : Number(event.target.value))} placeholder='No upper limit' data-testid={`bir-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='base_tax'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Base Tax (₱)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`bir-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='excess_rate'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Excess Rate (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`bir-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='effective_date'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Effective Date</FormLabel>
                  <FormControl>
                    <Input type='date' {...field} data-testid="bir-effective-date-input" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <SheetFooter>
              <SheetClose asChild>
                <Button type='button' variant='outline'>
                  Cancel
                </Button>
              </SheetClose>
              <Button type='submit' disabled={createMutation.isPending || updateMutation.isPending} data-testid="bir-submit-button">
                {item ? 'Update' : 'Create'}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  )
}
