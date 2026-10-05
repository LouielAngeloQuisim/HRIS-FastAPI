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
import { useCreatePagIBIGBracket, useUpdatePagIBIGBracket } from '@/lib/api/payroll-config'
import type { PagIBIGBracketPublic } from '@/lib/api/types'

const formSchema = z.object({
  salary_min: z.coerce.number<number>().min(0, 'Enter 0 or a positive value.'),
  salary_max: z.coerce.number<number>().min(0, 'Enter 0 or a positive value.'),
  employee_rate: z.coerce.number<number>().min(0, 'Enter 0 or a positive value.').max(100, 'Enter a percentage between 0 and 100.'),
  employer_rate: z.coerce.number<number>().min(0, 'Enter 0 or a positive value.').max(100, 'Enter a percentage between 0 and 100.'),
  effective_date: z.string().min(1, 'Select an effective date.'),
})
type FormData = z.infer<typeof formSchema>

interface Props {
  item: PagIBIGBracketPublic | null
  onClose: () => void
  open: boolean
}

export function PagIBIGResourceForm({ item, onClose, open }: Props) {
  const createMutation = useCreatePagIBIGBracket()
  const updateMutation = useUpdatePagIBIGBracket()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: item
      ? {
          salary_min: Number(item.salary_min),
          salary_max: Number(item.salary_max),
          employee_rate: Number(item.employee_rate),
          employer_rate: Number(item.employer_rate),
          effective_date: item.effective_date,
        }
      : {
          salary_min: 0,
          salary_max: 0,
          employee_rate: 0,
          employer_rate: 0,
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
          <SheetTitle>{item ? 'Edit Pag-IBIG Bracket' : 'Add Pag-IBIG Bracket'}</SheetTitle>
          <SheetDescription>
            {item ? 'Update the Pag-IBIG bracket configuration.' : 'Create a new Pag-IBIG bracket configuration.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-4 px-4 py-4'>
            {form.formState.errors.root?.server?.message && <p role='alert'>{form.formState.errors.root.server.message}</p>}
            <FormField
              control={form.control}
              name='salary_min'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Salary Min (₱)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`pagibig-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='salary_max'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Salary Max (₱)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`pagibig-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employee_rate'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employee Rate (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`pagibig-${field.name}-input`} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='employer_rate'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Employer Rate (%)</FormLabel>
                  <FormControl>
                    <Input type='number' step='0.01' {...field} data-testid={`pagibig-${field.name}-input`} />
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
                    <Input type='date' {...field} data-testid="pagibig-effective-date-input" />
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
              <Button type='submit' disabled={createMutation.isPending || updateMutation.isPending} data-testid="pagibig-submit-button">
                {item ? 'Update' : 'Create'}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  )
}
