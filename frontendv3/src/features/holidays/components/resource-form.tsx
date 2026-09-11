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
import { Switch } from '@/components/ui/switch'
import { useCreateHolidayConfig, useUpdateHolidayConfig } from '@/lib/api/holidays'
import type { HolidayConfigPublic, HolidayConfigCreate, HolidayConfigUpdate } from '@/lib/api/types'
import { toast } from 'sonner'

const formSchema = z.object({
  code: z.string().min(1, 'Code is required'),
  name: z.string().min(1, 'Name is required'),
  month_day: z.string().min(1, 'Month/Day is required'),
  type: z.enum(['regular', 'special', 'adobo']).default('regular'),
  region_code: z.string().optional(),
  is_recurring: z.boolean().default(true),
})

type FormData = z.infer<typeof formSchema>

interface Props {
  item: HolidayConfigPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, open, onClose }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateHolidayConfig()
  const updateMutation = useUpdateHolidayConfig()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      code: item?.code ?? '',
      name: item?.name ?? '',
      month_day: item?.month_day ?? '',
      type: 'regular',
      region_code: item?.region_code ?? '',
      is_recurring: item?.is_recurring ?? true,
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: data as unknown as HolidayConfigUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as HolidayConfigCreate)
      }
      onClose()
    } catch (err) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (err as any)?.response?.data?.detail ?? 'Failed to save holiday configuration'
      toast.error(detail)
    }
  }

  const loading = createMutation.isPending || updateMutation.isPending

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className="flex flex-col">
        <SheetHeader>
          <SheetTitle>{isEdit ? 'Update' : 'Create'} Holiday</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the holiday configuration.' : 'Add a new holiday configuration.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="holidays-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            <>
              <FormField control={form.control} name="code" render={({ field }) => (
                <FormItem>
                  <FormLabel>Code</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="holiday-code-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="holiday-name-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="month_day" render={({ field }) => (
                <FormItem>
                  <FormLabel>Month/Day</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} placeholder="e.g. 01-01" data-testid="holiday-month-day-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="type" render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value} data-testid="holiday-type-select">
                    <FormControl>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="regular">Regular</SelectItem>
                      <SelectItem value="special">Special</SelectItem>
                      <SelectItem value="adobo">Adobo</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="region_code" render={({ field }) => (
                <FormItem>
                  <FormLabel>Region Code</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="holiday-region-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="is_recurring" render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
                  <FormLabel>Recurring</FormLabel>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      data-testid="holiday-recurring-switch"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </>
          </form>
        </Form>
        <SheetFooter>
          <SheetClose asChild>
            <Button type="button" variant="outline">Cancel</Button>
          </SheetClose>
          <Button type="submit" form="holidays-form" disabled={loading} data-testid="holiday-submit-button">
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
