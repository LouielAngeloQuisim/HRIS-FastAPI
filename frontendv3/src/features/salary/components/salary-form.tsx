import { useState } from 'react'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useCreateSalary, useUpdateSalary, useDeleteSalary } from '@/lib/api/payroll'
import { toast } from 'sonner'
import { saveErrorMessage } from '@/lib/api/save-error'
import { ResourceDeleteDialog } from '@/components/resource-delete-dialog'
import type { EmployeeSalaryCreate, EmployeeSalaryUpdate, EmployeeSalaryPublic, PayType } from '@/lib/api/types'

const formSchema = z.object({
  basic_rate: z.string().min(1, 'Basic rate is required'),
  currency: z.string().max(3).optional().or(z.literal('')),
  effective_date: z.string().min(1, 'Effective date is required'),
  pay_type: z.string().max(10).optional().or(z.literal('')),
  overtime_rate: z.string().optional(),
  absent_penalty_rate: z.string().optional(),
  non_taxable_allowance: z.string().optional(),
  de_minimis_monthly: z.any().optional(),
  thirteenth_month_exempt_portion: z.string().optional(),
  is_active: z.boolean().optional(),
})
type FormData = z.infer<typeof formSchema>

interface Props {
  open: boolean
  onClose: () => void
  employeeId: string | undefined
  initialData?: EmployeeSalaryPublic
}

const DEFAULTS = {
  basic_rate: '',
  currency: 'PHP',
  effective_date: '',
  pay_type: 'monthly',
  overtime_rate: '0.000',
  absent_penalty_rate: '0.000',
  non_taxable_allowance: '0.00',
  de_minimis_monthly: {},
  thirteenth_month_exempt_portion: '90000.00',
  is_active: true,
} satisfies Record<keyof FormData, unknown>

export function SalaryForm({ open, onClose, employeeId, initialData }: Props) {
  const isEdit = Boolean(initialData?.id)
  const createMutation = useCreateSalary()
  const updateMutation = useUpdateSalary()
  const deleteMutation = useDeleteSalary()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const defaults = {
    ...DEFAULTS,
    basic_rate: initialData?.basic_rate ?? '',
    currency: initialData?.currency ?? 'PHP',
    effective_date: initialData?.effective_date ?? '',
    pay_type: initialData?.pay_type ?? 'monthly',
    overtime_rate: initialData?.overtime_rate ?? '0.000',
    absent_penalty_rate: initialData?.absent_penalty_rate ?? '0.000',
    non_taxable_allowance: initialData?.non_taxable_allowance ?? '0.00',
    thirteenth_month_exempt_portion: initialData?.thirteenth_month_exempt_portion ?? '90000.00',
    is_active: initialData?.is_active ?? true,
  }

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: defaults,
  })

  const loading = createMutation.isPending || updateMutation.isPending || deleting

  const onSubmit = async (data: FormData) => {
    form.clearErrors('root.server')
    try {
      const payload: EmployeeSalaryCreate = {
        employee_id: employeeId as string,
        basic_rate: data.basic_rate,
        currency: data.currency || 'PHP',
        effective_date: data.effective_date,
        pay_type: (data.pay_type as PayType) || 'monthly',
        overtime_rate: data.overtime_rate || '0.000',
        absent_penalty_rate: data.absent_penalty_rate || '0.000',
        non_taxable_allowance: data.non_taxable_allowance || '0.00',
        thirteenth_month_exempt_portion: data.thirteenth_month_exempt_portion || '90000.00',
        is_active: data.is_active ?? true,
      }
      if (isEdit && initialData?.id) {
        const updateData: Partial<EmployeeSalaryUpdate> = {}
        Object.entries(data).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(defaults[key as keyof FormData])).forEach(([key, value]) => {
          const payloadKey = key as keyof EmployeeSalaryUpdate
          updateData[payloadKey] = value
        })
        if (Object.keys(updateData).length === 0) {
          toast.warning('No changes were made.')
          onClose()
          return
        }
        await updateMutation.mutateAsync({ salary_id: initialData.id, salary: updateData })
        toast.success('Salary updated')
      } else {
        await createMutation.mutateAsync(payload)
        toast.success('Salary created')
      }
      form.reset()
      onClose()
    } catch (error) {
      form.setError('root.server', { message: saveErrorMessage(error) })
    }
  }

  const handleDelete = async () => {
    if (!initialData?.id) return
    setDeleting(true)
    try {
      await deleteMutation.mutateAsync({ salary_id: initialData.id, employee_id: employeeId ?? initialData.employee_id ?? '' })
      toast.success('Salary archived')
      setDeleteOpen(false)
      onClose()
    } catch (error) {
      toast.error(saveErrorMessage(error))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
        <SheetContent className='flex flex-col'>
          <SheetHeader>
            <SheetTitle>{isEdit ? 'Edit Salary' : 'Add Salary'}</SheetTitle>
            <SheetDescription>
              {isEdit
                ? 'Update the employee salary record below.'
                : 'Add a new effective-dated salary for the employee.'}
            </SheetDescription>
          </SheetHeader>
          <Form {...form}>
            <form id='salary-form' onSubmit={form.handleSubmit(onSubmit)} className='flex-1 space-y-6 overflow-y-auto px-4'>
              {form.formState.errors.root?.server?.message && (
                <div className='rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive'>
                  {form.formState.errors.root.server.message}
                </div>
              )}
              <div className='space-y-3'>
                <label className='text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70'>
                  Employee
                </label>
                <Input
                  disabled
                  value={employeeId || '—'}
                  data-testid='salary-form-employee-field'
                  aria-label='Employee'
                />
              </div>
              <div className='grid gap-4 sm:grid-cols-2'>
                <FormField
                  control={form.control}
                  name='basic_rate'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Basic Rate</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.01' {...field} value={field.value ?? ''} data-testid='salary-form-basic-rate-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='currency'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Currency</FormLabel>
                      <FormControl>
                        <Input maxLength={3} {...field} value={field.value ?? ''} data-testid='salary-form-currency-input' />
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
                        <Input type='date' {...field} value={field.value ?? ''} data-testid='salary-form-effective-date-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='pay_type'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Pay Type</FormLabel>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger data-testid='salary-form-pay-type-select'>
                            <SelectValue placeholder='Select pay type' />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value='monthly'>Monthly</SelectItem>
                          <SelectItem value='daily'>Daily</SelectItem>
                          <SelectItem value='hourly'>Hourly</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='overtime_rate'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Overtime Rate</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.000' {...field} value={field.value ?? ''} data-testid='salary-form-overtime-rate-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='absent_penalty_rate'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Absent Penalty Rate</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.000' {...field} value={field.value ?? ''} data-testid='salary-form-absent-penalty-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='non_taxable_allowance'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Fixed Monthly Allowance</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.01' {...field} value={field.value ?? ''} data-testid='salary-form-non-taxable-input' />
                      </FormControl>
                      <p className='text-xs text-muted-foreground'>
                        Taxable under the confirmed payroll policy; prorated by employed calendar days and not reduced for attendance. Enter de minimis benefits in the tax-benefits ledger.
                      </p>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='thirteenth_month_exempt_portion'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>13th Month Exempt Portion</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.01' {...field} value={field.value ?? ''} data-testid='salary-form-13month-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='is_active'
                  render={({ field }) => (
                    <FormItem className='flex flex-row items-center gap-3'>
                      <FormControl>
                        <input
                          type='checkbox'
                          checked={Boolean(field.value)}
                          onChange={(e) => field.onChange(e.target.checked)}
                          data-testid='salary-form-active-checkbox'
                        />
                      </FormControl>
                      <FormLabel className='mb-0'>Active</FormLabel>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </form>
          </Form>
          <SheetFooter className='gap-2'>
            <SheetClose asChild>
              <Button type='button' variant='outline'>Cancel</Button>
            </SheetClose>
            {isEdit && (
              <Button
                type='button'
                variant='destructive'
                onClick={() => setDeleteOpen(true)}
                disabled={loading}
                data-testid='salary-form-archive-button'
              >
                {deleting ? 'Archiving...' : 'Archive'}
              </Button>
            )}
            <Button type='submit' form='salary-form' disabled={loading} data-testid='salary-form-submit-button'>
              {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
      {isEdit && (
        <ResourceDeleteDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          entityName='Salary'
          entityLabel={`${initialData?.basic_rate ?? ''} / ${initialData?.effective_date ?? ''}`}
          onConfirm={handleDelete}
          isPending={deleting}
        />
      )}
    </>
  )
}
