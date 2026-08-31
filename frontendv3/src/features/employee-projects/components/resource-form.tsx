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
import { useCreateEmployeeProject, useUpdateEmployeeProject } from '@/lib/api/employee-projects'
import type { EmployeeProjectsPublic, EmployeeProjectsCreate, EmployeeProjectsUpdate } from '@/lib/api/types'

const formSchema = z.object({
  employee_id: z.string().optional(),
  project_id: z.string().optional(),
  date: z.string().optional(),
  rendered_hours: z.string().optional(),
  task: z.string().optional(),
  is_assigned: z.string().optional(),
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FormData = any

interface Props {
  item: EmployeeProjectsPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateEmployeeProject()
  const updateMutation = useUpdateEmployeeProject()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      employee_id: item?.employee_id ?? '',
      project_id: item?.project_id ?? '',
      date: item?.date ?? '',
      rendered_hours: item?.rendered_hours ?? '',
      task: item?.task ?? '',
      is_assigned: item?.is_assigned ?? '',
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: data as unknown as EmployeeProjectsUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as EmployeeProjectsCreate)
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
          <SheetTitle>{isEdit ? 'Update' : 'Create'} EmployeeProjects</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the employee project by providing necessary info.' : 'Add a new employee project by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="employee-projects-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            <>
              <FormField control={form.control} name="employee_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Employee</FormLabel>
                  <FormControl>
                    <SelectDropdown
                      defaultValue={field.value}
                      onValueChange={field.onChange}
                      placeholder="Select employee"
                      items={[]}
                      isPending={false}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="project_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Project</FormLabel>
                  <FormControl>
                    <SelectDropdown
                      defaultValue={field.value}
                      onValueChange={field.onChange}
                      placeholder="Select project"
                      items={[]}
                      isPending={false}
                    />
                  </FormControl>
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
              <FormField control={form.control} name="rendered_hours" render={({ field }) => (
                <FormItem>
                  <FormLabel>Rendered Hours</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="task" render={({ field }) => (
                <FormItem>
                  <FormLabel>Task</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="is_assigned" render={({ field }) => (
                <FormItem>
                  <FormLabel>Assigned</FormLabel>
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
          <Button type="submit" form="employee-projects-form" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
