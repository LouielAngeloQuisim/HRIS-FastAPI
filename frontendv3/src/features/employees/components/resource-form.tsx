import { useEffect, useMemo, useState } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreateEmployee, useUpdateEmployee, useDeleteEmployee } from '@/lib/api/employees'
import { toast } from 'sonner'
import { saveErrorMessage } from '@/lib/api/save-error'
import { ResourceDeleteDialog } from '@/components/resource-delete-dialog'
import type { EmployeeRecordsPublic, EmployeeRecordsCreate, EmployeeRecordsUpdate } from '@/lib/api/types'

const formSchema = z.object({
  employee_code: z.string().min(1, 'Employee code is required'),
  first_name: z.string().min(1, 'First name is required'),
  middle_name: z.string().optional(),
  last_name: z.string().min(1, 'Last name is required'),
  extension: z.string().optional(),
  birthdate: z.string().min(1, 'Birthdate is required'),
  birth_place: z.string().optional(),
  gender: z.string().optional(),
  civil_status: z.string().optional(),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
  zip_code: z.string().optional(),
  area: z.string().optional(),
  present_barangay: z.string().optional(),
  present_city: z.string().optional(),
  same_address: z.boolean().optional(),
  permanent_barangay: z.string().optional(),
  permanent_city: z.string().optional(),
  date_hired: z.string().optional(),
  employee_status: z.string().optional(),
  employment_type: z.string().optional(),
  contract_expiry_date: z.string().optional(),
  date_separated: z.string().optional(),
  probationary_date: z.string().optional(),
  regularization_date: z.string().optional(),
  telephone: z.string().optional(),
  cellphone: z.string().optional(),
  profile_photo_path: z.string().optional(),
  position_id: z.string().optional(),
  division_id: z.string().optional(),
  department_id: z.string().optional(),
})
type FormData = z.infer<typeof formSchema>

interface Props {
  item: EmployeeRecordsPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateEmployee()
  const updateMutation = useUpdateEmployee()
  const deleteMutation = useDeleteEmployee()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const defaults = useMemo(() => ({
    employee_code: item?.employee_code ?? '',
    first_name: item?.first_name ?? '',
    middle_name: item?.middle_name ?? '',
    last_name: item?.last_name ?? '',
    extension: item?.extension ?? '',
    birthdate: item?.birthdate ?? '',
    birth_place: item?.birth_place ?? '',
    gender: item?.gender ?? '',
    civil_status: item?.civil_status ?? '',
    email: item?.email ?? '',
    zip_code: item?.zip_code ?? '',
    area: item?.area ?? '',
    present_barangay: item?.present_barangay ?? '',
    present_city: item?.present_city ?? '',
    same_address: item?.same_address ?? false,
    permanent_barangay: item?.permanent_barangay ?? '',
    permanent_city: item?.permanent_city ?? '',
    date_hired: item?.date_hired ?? '',
    employee_status: item?.employee_status ?? '',
    employment_type: item?.employment_type ?? '',
    contract_expiry_date: item?.contract_expiry_date ?? '',
    date_separated: item?.date_separated ?? '',
    probationary_date: item?.probationary_date ?? '',
    regularization_date: item?.regularization_date ?? '',
    telephone: item?.telephone ?? '',
    cellphone: item?.cellphone ?? '',
    profile_photo_path: item?.profile_photo_path ?? '',
    position_id: item?.position_id ?? '',
    division_id: item?.division_id ?? '',
    department_id: item?.department_id ?? '',
  }), [item])

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: defaults,
  })

  useEffect(() => {
    if (open) form.reset(defaults)
  }, [defaults, form, open])

  const loading = createMutation.isPending || updateMutation.isPending || deleting

  const onSubmit = async (data: FormData) => {
    form.clearErrors('root.server')
    try {
      if (isEdit && item?.id) {
        const updateData = Object.fromEntries(
          Object.entries(data)
            .filter(([key, value]) => value !== defaults[key as keyof FormData])
            .map(([key, value]) => [
              key,
              value === '' && ['birthdate', 'date_hired', 'contract_expiry_date', 'date_separated', 'probationary_date', 'regularization_date', 'position_id', 'division_id', 'department_id'].includes(key)
                ? null
                : value,
            ])
        ) as Partial<EmployeeRecordsUpdate>
        if (Object.keys(updateData).length === 0) {
          toast.warning('No changes were made.')
          onClose()
          return
        }
        await updateMutation.mutateAsync({ id: item.id, data: updateData })
        toast.success('Employee updated')
      } else {
        // Blank optional inputs (especially UUID, enum, and date fields) are
        // invalid API values. Omit them so backend defaults/nulls apply.
        const { employee_code, first_name, last_name, birthdate, ...optional } = data
        const createData: EmployeeRecordsCreate = {
          employee_code,
          first_name,
          last_name,
          birthdate,
          ...Object.fromEntries(Object.entries(optional).filter(([, value]) => value !== '')),
        }
        await createMutation.mutateAsync(createData)
        toast.success('Employee created')
      }
      form.reset()
      onClose()
    } catch (error) {
      form.setError('root.server', { message: saveErrorMessage(error) })
    }
  }

  const handleDelete = async () => {
    if (!item?.id) return
    setDeleting(true)
    try {
      await deleteMutation.mutateAsync(item.id)
      toast.success('Employee archived')
      setDeleteOpen(false)
      onClose()
    } catch (error) {
      toast.error(saveErrorMessage(error))
    } finally {
      setDeleting(false)
    }
  }

  const fields = [
    {
      section: 'Core information',
      rows: [
        { key: 'employee_code', label: 'Employee Code', type: 'text', testid: 'resource-form-employee-code-input' },
        { key: 'first_name', label: 'First Name', type: 'text', testid: 'resource-form-first-name-input' },
        { key: 'middle_name', label: 'Middle Name', type: 'text', testid: 'resource-form-middle-name-input' },
        { key: 'last_name', label: 'Last Name', type: 'text', testid: 'resource-form-last-name-input' },
        { key: 'extension', label: 'Extension', type: 'text', testid: 'resource-form-extension-input' },
        { key: 'birthdate', label: 'Birthdate', type: 'date', testid: 'resource-form-birthdate-input' },
        { key: 'birth_place', label: 'Birth Place', type: 'text', testid: 'resource-form-birth-place-input' },
        { key: 'gender', label: 'Gender', type: 'text', testid: 'resource-form-gender-input' },
        { key: 'civil_status', label: 'Civil Status', type: 'text', testid: 'resource-form-civil-status-input' },
      ],
    },
    {
      section: 'Contact & address',
      rows: [
        { key: 'email', label: 'Email', type: 'email', testid: 'resource-form-email-input' },
        { key: 'zip_code', label: 'ZIP Code', type: 'text', testid: 'resource-form-zip-code-input' },
        { key: 'area', label: 'Area', type: 'text', testid: 'resource-form-area-input' },
        { key: 'present_barangay', label: 'Present Barangay', type: 'text', testid: 'resource-form-present-barangay-input' },
        { key: 'present_city', label: 'Present City', type: 'text', testid: 'resource-form-present-city-input' },
        { key: 'same_address', label: 'Same as present address', type: 'boolean', testid: 'resource-form-same-address-checkbox' },
        { key: 'permanent_barangay', label: 'Permanent Barangay', type: 'text', testid: 'resource-form-permanent-barangay-input' },
        { key: 'permanent_city', label: 'Permanent City', type: 'text', testid: 'resource-form-permanent-city-input' },
      ],
    },
    {
      section: 'Employment',
      rows: [
        { key: 'date_hired', label: 'Date Hired', type: 'date', testid: 'resource-form-date-hired-input' },
        { key: 'employee_status', label: 'Employee Status', type: 'select', options: ['Active', 'Resigned', 'Terminated', 'On Leave'], testid: 'resource-form-employee-status-select' },
        { key: 'employment_type', label: 'Employment Type', type: 'text', testid: 'resource-form-employment-type-input' },
        { key: 'contract_expiry_date', label: 'Contract Expiry Date', type: 'date', testid: 'resource-form-contract-expiry-input' },
        { key: 'date_separated', label: 'Date Separated', type: 'date', testid: 'resource-form-date-separated-input' },
        { key: 'probationary_date', label: 'Probationary Date', type: 'date', testid: 'resource-form-probationary-date-input' },
        { key: 'regularization_date', label: 'Regularization Date', type: 'date', testid: 'resource-form-regularization-date-input' },
        { key: 'position_id', label: 'Position', type: 'text', testid: 'resource-form-position-id-input' },
        { key: 'division_id', label: 'Division', type: 'text', testid: 'resource-form-division-id-input' },
        { key: 'department_id', label: 'Department', type: 'text', testid: 'resource-form-department-id-input' },
      ],
    },
    {
      section: 'Contact numbers (optional)',
      rows: [
        { key: 'telephone', label: 'Telephone', type: 'text', testid: 'resource-form-telephone-input' },
        { key: 'cellphone', label: 'Cellphone', type: 'text', testid: 'resource-form-cellphone-input' },
      ],
    },
  ] as const

  type EmployeeResourceFormFieldRow = (typeof fields)[number]['rows'][number]

  return (
    <>
      <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
        <SheetContent className='flex flex-col'>
          <SheetHeader>
            <SheetTitle>{isEdit ? 'Edit Employee' : 'Add Employee'}</SheetTitle>
            <SheetDescription>
              {isEdit ? 'Update the employee record below.' : 'Add a new employee to the organization.'}
            </SheetDescription>
          </SheetHeader>
          <Form {...form}>
            <form id='resource-form' onSubmit={form.handleSubmit(onSubmit)} className='flex-1 space-y-6 overflow-y-auto px-4'>
              {form.formState.errors.root?.server?.message && (
                <div className='rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive'>
                  {form.formState.errors.root.server.message}
                </div>
              )}
              {fields.map((group) => (
                <div key={group.section} className='space-y-3'>
                  <h3 className='text-sm font-semibold uppercase tracking-wide text-muted-foreground'>{group.section}</h3>
                  <div className='grid gap-4 sm:grid-cols-2'>
                    {group.rows.map(({ key, label, type, testid }: EmployeeResourceFormFieldRow) => (
                      <FormField
                        key={key}
                        control={form.control}
                        name={key}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{label}</FormLabel>
                            {type === 'select' ? (
                              <Select value={field.value as string} onValueChange={field.onChange}>
                                <FormControl>
                                  <SelectTrigger data-testid={testid}>
                                    <SelectValue placeholder={`Select ${label.toLowerCase()}`} />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {group.rows.filter(r => r.type === 'select').map((r) => (
                                    r.options?.map((opt) => (
                                      <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                                    )) || []
                                  ))}
                                </SelectContent>
                              </Select>
                            ) : type === 'boolean' ? (
                              <FormControl>
                                <Input
                                  type='checkbox'
                                  checked={Boolean(field.value)}
                                  onChange={(e) => field.onChange(e.target.checked)}
                                  data-testid={testid}
                                />
                              </FormControl>
                            ) : type === 'date' ? (
                              <FormControl>
                                <Input
                                  type='date'
                                  value={(field.value ?? '') as string}
                                  onChange={(e) => field.onChange(e.target.value)}
                                  data-testid={testid}
                                />
                              </FormControl>
                            ) : type === 'email' ? (
                              <FormControl>
                                <Input
                                  type='email'
                                  value={(field.value ?? '') as string}
                                  onChange={(e) => field.onChange(e.target.value)}
                                  data-testid={testid}
                                />
                              </FormControl>
                            ) : (
                              <FormControl>
                                <Input
                                  value={(field.value ?? '') as string}
                                  onChange={(e) => field.onChange(e.target.value)}
                                  data-testid={testid}
                                />
                              </FormControl>
                            )}
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    ))}
                  </div>
                </div>
              ))}
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
                data-testid='resource-form-archive-button'
              >
                {deleting ? 'Archiving...' : 'Archive Employee'}
              </Button>
            )}
            <Button type='submit' form='resource-form' disabled={loading} data-testid='resource-form-submit-button'>
              {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
      {isEdit && (
        <ResourceDeleteDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          entityName='Employee'
          entityLabel={`${item?.first_name ?? ''} ${item?.last_name ?? ''} (${item?.employee_code ?? ''})`}
          onConfirm={handleDelete}
          isPending={deleting}
          data-testid='resource-form-archive-dialog'
        />
      )}
    </>
  )
}
