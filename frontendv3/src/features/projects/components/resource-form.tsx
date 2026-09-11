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
import { useCreateProject, useUpdateProject } from '@/lib/api/projects'
import { useProjectTypes } from '@/lib/api/project-types'
import { useSubdivisions } from '@/lib/api/subdivisions'
import type { ProjectPublic, ProjectCreate, ProjectUpdate } from '@/lib/api/types'

const formSchema = z.object({
  code: z.string().optional(),
  name: z.string().optional(),
  description: z.string().optional(),
  subdivision_id: z.string().optional(),
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FormData = any

interface Props {
  item: ProjectPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateProject()
  const updateMutation = useUpdateProject()
  const { data: projectTypeData, isPending: projectTypesPending } = useProjectTypes(1, 100)
  const { data: subdivisionData, isPending: subdivisionsPending } = useSubdivisions(1, 100)

  const projectTypeItems = projectTypeData?.data.map((pt) => ({
    label: pt.name,
    value: pt.id,
  }))

  const subdivisionItems = subdivisionData?.data.map((sub) => ({
    label: sub.name,
    value: sub.id,
  }))

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      code: item?.code ?? '',
      name: item?.name ?? '',
      description: item?.description ?? '',
      subdivision_id: item?.subdivision_id ?? '',
      project_type_id: item?.project_type_id ?? '',
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: data as unknown as ProjectUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as ProjectCreate)
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
          <SheetTitle>{isEdit ? 'Update' : 'Create'} Project</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the project by providing necessary info.' : 'Add a new project by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="projects-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            <>
              <FormField control={form.control} name="code" render={({ field }) => (
                <FormItem>
                  <FormLabel>Code</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="project-code-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="project-name-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="description" render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="project-description-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="subdivision_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Subdivision</FormLabel>
                  <FormControl>
                     <SelectDropdown
                       defaultValue={field.value}
                       onValueChange={field.onChange}
                       placeholder="Select subdivision"
                       items={subdivisionItems ?? []}
                       isPending={subdivisionsPending}
                       data-testid="project-subdivision-select"
                     />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="project_type_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Project Type</FormLabel>
                  <FormControl>
                     <SelectDropdown
                       defaultValue={field.value}
                       onValueChange={field.onChange}
                       placeholder="Select project type"
                       items={projectTypeItems ?? []}
                       isPending={projectTypesPending}
                       data-testid="project-type-select"
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
          <Button type="submit" form="projects-form" disabled={loading} data-testid="project-submit-button">
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
