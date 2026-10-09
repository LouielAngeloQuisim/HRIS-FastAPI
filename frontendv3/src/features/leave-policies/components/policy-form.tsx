import { useEffect, useMemo, useRef, type FormEvent } from 'react'
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
import { useCreateLeavePolicy, useUpdateLeavePolicy } from '@/lib/api/leave-policies'
import { toast } from 'sonner'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { LeavePolicyCreate, LeavePolicyUpdate, LeavePolicyPublic, LeaveCadence, GenderScope, MaritalStatusScope } from '@/lib/api/types'

// Value-based deep equality for primitives, arrays, and plain objects (react-hook-form
// deep-clones defaultValues, so reference-equality does not work for array fields).
function deepEquals(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => deepEquals(v, b[i]))
  }
  if (
    typeof a === 'object' &&
    typeof b === 'object' &&
    a !== null &&
    b !== null &&
    !Array.isArray(a) &&
    !Array.isArray(b)
  ) {
    const left = a as Record<string, unknown>
    const right = b as Record<string, unknown>
    const ka = Object.keys(left)
    const kb = Object.keys(right)
    return ka.length === kb.length && ka.every((k) => deepEquals(left[k], right[k]))
  }
  return false
}

const formSchema = z.object({
  code: z.string().min(1, 'Policy code is required'),
  name: z.string().min(1, 'Policy name is required'),
  description: z.string().optional(),
  calendar_color: z.string().max(7).optional().or(z.literal('')),
  cadence: z.string().max(10).optional().or(z.literal('')),
  annual_entitlement_days: z.string().optional(),
  prorate_on_hire: z.boolean().optional(),
  carry_over_enabled: z.boolean().optional(),
  carry_over_max_days: z.string().optional(),
  carry_over_expires_on: z.string().optional(),
  is_paid: z.boolean().optional(),
  tax_exempt_unused_vacation_leave: z.boolean().optional(),
  eligible_departments: z.array(z.string()).optional(),
  gender_scope: z.string().max(6).optional().or(z.literal('')),
  marital_status_scope: z.string().max(9).optional().or(z.literal('')),
  is_active: z.boolean().optional(),
})
type FormData = z.infer<typeof formSchema>

interface Props {
  open: boolean
  onClose: () => void
  initialData?: LeavePolicyPublic
}

const DEFAULTS = {
  code: '',
  name: '',
  description: '',
  calendar_color: '#3B82F6',
  cadence: 'annual',
  annual_entitlement_days: '0.00',
  prorate_on_hire: false,
  carry_over_enabled: false,
  carry_over_max_days: '',
  carry_over_expires_on: '',
  is_paid: true,
  tax_exempt_unused_vacation_leave: false,
  eligible_departments: [],
  gender_scope: 'all',
  marital_status_scope: 'all',
  is_active: true,
} satisfies Record<keyof FormData, unknown>

export function LeavePolicyForm({ open, onClose, initialData }: Props) {
  const isEdit = Boolean(initialData?.id)
  const createMutation = useCreateLeavePolicy()
  const updateMutation = useUpdateLeavePolicy()
  const loading = createMutation.isPending || updateMutation.isPending

  const defaults = useMemo(() => ({
    ...DEFAULTS,
    code: initialData?.code ?? '',
    name: initialData?.name ?? '',
    description: initialData?.description ?? '',
    calendar_color: initialData?.calendar_color ?? '#3B82F6',
    cadence: initialData?.cadence ?? 'annual',
    annual_entitlement_days: initialData?.annual_entitlement_days ?? '0.00',
    prorate_on_hire: initialData?.prorate_on_hire ?? false,
    carry_over_enabled: initialData?.carry_over_enabled ?? false,
    carry_over_max_days: initialData?.carry_over_max_days ?? '',
    carry_over_expires_on: initialData?.carry_over_expires_on ?? '',
    is_paid: initialData?.is_paid ?? true,
    tax_exempt_unused_vacation_leave: initialData?.tax_exempt_unused_vacation_leave ?? false,
    eligible_departments: initialData?.eligible_departments ?? [],
    gender_scope: initialData?.gender_scope ?? 'all',
    marital_status_scope: initialData?.marital_status_scope ?? 'all',
    is_active: initialData?.is_active ?? true,
  }), [initialData])

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: defaults,
  })

  // Track the baseline alongside resets when the dialog switches between
  // create and edit records, so only user-edited fields are sent.
  const baseline = useRef<FormData>(defaults)

  useEffect(() => {
    if (!open) return
    form.reset(defaults)
    baseline.current = defaults
  }, [baseline, defaults, form, open])

  const onSubmit = async (data: FormData) => {
    form.clearErrors('root.server')
    try {
      const payload: LeavePolicyCreate = {
        code: data.code,
        name: data.name,
        description: data.description || undefined,
        calendar_color: data.calendar_color || undefined,
        cadence: (data.cadence as LeaveCadence) || 'annual',
        annual_entitlement_days: data.annual_entitlement_days || undefined,
        prorate_on_hire: data.prorate_on_hire,
        carry_over_enabled: data.carry_over_enabled,
        carry_over_max_days: data.carry_over_max_days || undefined,
        carry_over_expires_on: data.carry_over_expires_on || undefined,
        is_paid: data.is_paid,
        tax_exempt_unused_vacation_leave: data.tax_exempt_unused_vacation_leave,
        eligible_departments: data.eligible_departments || [],
        gender_scope: (data.gender_scope as GenderScope) || 'all',
        marital_status_scope: (data.marital_status_scope as MaritalStatusScope) || 'all',
        is_active: data.is_active,
      }
      if (isEdit && initialData?.id) {
        const updateData: Record<string, unknown> = {}
        Object.entries(payload).forEach(([key, value]) => {
          const original = baseline.current[key as keyof FormData]
          if (deepEquals(value, original) || (value === undefined && original === '')) return
          updateData[key] = value
        })
        if (Object.keys(updateData).length === 0) {
          toast.warning('No changes were made.')
          onClose()
          return
        }
        await updateMutation.mutateAsync({ id: initialData.id, data: updateData as LeavePolicyUpdate })
        toast.success('Leave policy updated')
      } else {
        await createMutation.mutateAsync(payload)
        toast.success('Leave policy created')
      }
      form.reset()
      onClose()
    } catch (error) {
      form.setError('root.server', { message: saveErrorMessage(error) })
    }
  }

  const handleFormSubmit = (event: FormEvent<HTMLFormElement>) => {
    void form.handleSubmit(onSubmit)(event)
  }

  return (
    <>
      <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
        <SheetContent className='flex flex-col'>
          <SheetHeader>
            <SheetTitle>{isEdit ? 'Edit Leave Policy' : 'Add Leave Policy'}</SheetTitle>
            <SheetDescription>
              {isEdit
                ? 'Update the leave policy settings below.'
                : 'Create a new leave policy for employees.'}
            </SheetDescription>
          </SheetHeader>
          <Form {...form}>
            <form id='leave-policy-form' onSubmit={handleFormSubmit} className='flex-1 space-y-6 overflow-y-auto px-4'>
              {form.formState.errors.root?.server?.message && (
                <div className='rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive'>
                  {form.formState.errors.root.server.message}
                </div>
              )}
              <div className='grid gap-4 sm:grid-cols-2'>
                <FormField
                  control={form.control}
                  name='code'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Policy Code</FormLabel>
                      <FormControl>
                        <Input {...field} value={field.value ?? ''} data-testid='policy-form-code-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='name'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Policy Name</FormLabel>
                      <FormControl>
                        <Input {...field} value={field.value ?? ''} data-testid='policy-form-name-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='calendar_color'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Calendar Color</FormLabel>
                      <FormControl>
                        <Input type='color' {...field} value={field.value ?? '#3B82F6'} data-testid='policy-form-calendar-color-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='cadence'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cadence</FormLabel>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger data-testid='policy-form-cadence-select'>
                            <SelectValue placeholder='Select cadence' />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value='annual'>Annual</SelectItem>
                          <SelectItem value='monthly'>Monthly</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='annual_entitlement_days'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Annual Entitlement (days)</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.01' {...field} value={field.value ?? ''} data-testid='policy-form-entitlement-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='carry_over_max_days'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Carry-over Max Days</FormLabel>
                      <FormControl>
                        <Input type='number' step='0.01' {...field} value={field.value ?? ''} data-testid='policy-form-carry-over-max-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='carry_over_expires_on'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Carry-over Expires On</FormLabel>
                      <FormControl>
                        <Input type='date' {...field} value={field.value ?? ''} data-testid='policy-form-carry-over-expires-input' />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='gender_scope'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Gender Scope</FormLabel>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger data-testid='policy-form-gender-scope-select'>
                            <SelectValue placeholder='Select gender scope' />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value='all'>All</SelectItem>
                          <SelectItem value='male'>Male</SelectItem>
                          <SelectItem value='female'>Female</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='marital_status_scope'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Marital Status Scope</FormLabel>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger data-testid='policy-form-marital-scope-select'>
                            <SelectValue placeholder='Select marital status scope' />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value='all'>All</SelectItem>
                          <SelectItem value='single'>Single</SelectItem>
                          <SelectItem value='married'>Married</SelectItem>
                          <SelectItem value='widowed'>Widowed</SelectItem>
                          <SelectItem value='divorced'>Divorced</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name='description'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Input {...field} value={field.value ?? ''} data-testid='policy-form-description-input' />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className='space-y-3'>
                <FormField
                  control={form.control}
                  name='prorate_on_hire'
                  render={({ field }) => (
                    <FormItem className='flex flex-row items-center gap-3'>
                      <FormControl>
                        <input
                          type='checkbox'
                          checked={Boolean(field.value)}
                          onChange={(e) => field.onChange(e.target.checked)}
                          data-testid='policy-form-prorate-checkbox'
                        />
                      </FormControl>
                      <FormLabel className='mb-0'>Prorate on Hire</FormLabel>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='carry_over_enabled'
                  render={({ field }) => (
                    <FormItem className='flex flex-row items-center gap-3'>
                      <FormControl>
                        <input
                          type='checkbox'
                          checked={Boolean(field.value)}
                          onChange={(e) => field.onChange(e.target.checked)}
                          data-testid='policy-form-carry-over-checkbox'
                        />
                      </FormControl>
                      <FormLabel className='mb-0'>Enable Carry-over</FormLabel>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='is_paid'
                  render={({ field }) => (
                    <FormItem className='flex flex-row items-center gap-3'>
                      <FormControl>
                        <input
                          type='checkbox'
                          checked={Boolean(field.value)}
                          onChange={(e) => field.onChange(e.target.checked)}
                          data-testid='policy-form-is-paid-checkbox'
                        />
                      </FormControl>
                      <FormLabel className='mb-0'>Paid Leave</FormLabel>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='tax_exempt_unused_vacation_leave'
                  render={({ field }) => (
                    <FormItem className='flex flex-row items-start gap-3'>
                      <FormControl>
                        <input
                          type='checkbox'
                          checked={Boolean(field.value)}
                          onChange={(e) => field.onChange(e.target.checked)}
                          data-testid='policy-form-tax-exempt-vacation-checkbox'
                        />
                      </FormControl>
                      <div>
                        <FormLabel className='mb-0'>Qualifies as unused vacation leave for BIR exemption</FormLabel>
                        <p className='text-xs text-muted-foreground'>Enable only for a paid vacation-leave policy whose balance is maintained in the leave ledger.</p>
                      </div>
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
                          data-testid='policy-form-is-active-checkbox'
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
            <Button type='submit' form='leave-policy-form' disabled={loading} data-testid='policy-form-submit-button'>
              {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  )
}
