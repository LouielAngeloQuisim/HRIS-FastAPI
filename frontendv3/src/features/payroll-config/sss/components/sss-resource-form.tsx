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
import { useCreateSSSBracket, useUpdateSSSBracket } from '@/lib/api/payroll-config'
import type { SSSBracketPublic } from '@/lib/api/types'

const formSchema = z.object({
  msc_min: z.coerce.number<number>().min(0),
  msc_max: z.coerce.number<number>().min(0),
  employer_ss: z.coerce.number<number>().min(0).max(100),
  employer_ec: z.coerce.number<number>().min(0),
  employer_mpf: z.coerce.number<number>().min(0).max(100),
  employee_ss: z.coerce.number<number>().min(0).max(100),
  employee_mpf: z.coerce.number<number>().min(0).max(100),
  effective_date: z.string().min(1),
})
type FormData = z.infer<typeof formSchema>

interface Props {
  item: SSSBracketPublic | null
  onClose: () => void
  open: boolean
}

export function SSSResourceForm({ item, onClose, open }: Props) {
  const createMutation = useCreateSSSBracket()
  const updateMutation = useUpdateSSSBracket()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: item
      ? {
          msc_min: Number(item.msc_min),
          msc_max: Number(item.msc_max),
          employer_ss: Number(item.employer_ss),
          employer_ec: Number(item.employer_ec),
          employer_mpf: Number(item.employer_mpf),
          employee_ss: Number(item.employee_ss),
          employee_mpf: Number(item.employee_mpf),
          effective_date: item.effective_date,
        }
      : {
          msc_min: 0,
          msc_max: 0,
          employer_ss: 0,
          employer_ec: 0,
          employer_mpf: 0,
          employee_ss: 0,
          employee_mpf: 0,
          effective_date: '',
        },
  })

  const onSubmit = async (data: FormData) => {
    try {
      if (item) {
        await updateMutation.mutateAsync({ id: item.id, data })
      } else {
        await createMutation.mutateAsync(data)
      }
      onClose()
    } catch {
      // error handled by mutation
    }
  }

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className='w-full overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{item ? 'Edit SSS Bracket' : 'Add SSS Bracket'}</SheetTitle>
          <SheetDescription>
            {item ? 'Update the SSS bracket configuration.' : 'Create a new SSS bracket configuration.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-4 px-4 py-4'>
            <FormField
              control={form.control}
              name='msc_min'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>MSC Min</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='msc_max'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>MSC Max</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employer_ss'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employer SS (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employer_ec'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employer EC (₱)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employer_mpf'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employer MPF (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employee_ss'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employee SS (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employee_mpf'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employee MPF (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`sss-${field.name}-input`} />
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
                    <Input type='date' {...field} data-testid="sss-effective-date-input" />
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
              <Button type='submit' disabled={createMutation.isPending || updateMutation.isPending} data-testid="sss-submit-button">
                {item ? 'Update' : 'Create'}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  )
}
