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
import { SelectDropdown } from '@/components/select-dropdown'
import { useCreateEmpTask, useUpdateEmpTask } from '@/lib/api/emp-tasks'
import type { EmpTaskPublic, EmpTaskCreate, EmpTaskUpdate } from '@/lib/api/types'

const formSchema = z.object({
  emp_project_id: z.string().optional(),
  task_desc: z.string().optional(),
  rendered_hours: z.string().optional(),
  assigned_hours: z.string().optional(),
  date: z.string().optional(),
  approved: z.string().optional(),
  is_adjusted: z.string().optional(),
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FormData = any

interface Props {
  item: EmpTaskPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateEmpTask()
  const updateMutation = useUpdateEmpTask()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      emp_project_id: item?.emp_project_id ?? '',
      task_desc: item?.task_desc ?? '',
      rendered_hours: item?.rendered_hours ?? '',
      assigned_hours: item?.assigned_hours ?? '',
      date: item?.date ?? '',
      approved: item?.approved ?? '',
      is_adjusted: item?.is_adjusted ?? '',
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: data as unknown as EmpTaskUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as EmpTaskCreate)
      }
      onClose()
    } catch (_e) {
      // _e is caught error
    }
  }

  const loading = createMutation.isPending || updateMutation.isPending

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className="flex flex-col">
        <SheetHeader>
          <SheetTitle>{isEdit ? 'Update' : 'Create'} EmpTask</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the emp task by providing necessary info.' : 'Add a new emp task by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="emp-tasks-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            <>
              <FormField control={form.control} name="emp_project_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Employee Project</FormLabel>
                  <FormControl>
                    <SelectDropdown
                      defaultValue={field.value}
                      onValueChange={field.onChange}
                      placeholder="Select employee project"
                      items={[]}
                      isPending={false}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="task_desc" render={({ field }) => (
                <FormItem>
                  <FormLabel>Task Description</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="rendered_hours" render={({ field }) => (
                <FormItem>
                  <FormLabel>Rendered Hours</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="assigned_hours" render={({ field }) => (
                <FormItem>
                  <FormLabel>Assigned Hours</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="date" render={({ field }) => (
                <FormItem>
                  <FormLabel>Date</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="approved" render={({ field }) => (
                <FormItem>
                  <FormLabel>Approved</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="is_adjusted" render={({ field }) => (
                <FormItem>
                  <FormLabel>Adjusted</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
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
          <Button type="submit" form="emp-tasks-form" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
