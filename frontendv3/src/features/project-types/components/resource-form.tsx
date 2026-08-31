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
import { useCreateProjectType, useUpdateProjectType } from '@/lib/api/project-types'
import type { ProjectTypePublic, ProjectTypeCreate, ProjectTypeUpdate } from '@/lib/api/types'

const formSchema = z.object({
  code: z.string().optional(),
  name: z.string().optional(),
  description: z.string().optional(),
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FormData = any

interface Props {
  item: ProjectTypePublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateProjectType()
  const updateMutation = useUpdateProjectType()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      code: item?.code ?? '',
      name: item?.name ?? '',
      description: item?.description ?? '',
    },
  })

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: data as unknown as ProjectTypeUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as ProjectTypeCreate)
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
          <SheetTitle>{isEdit ? 'Update' : 'Create'} ProjectType</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the project type by providing necessary info.' : 'Add a new project type by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="project-types-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            <>
              <FormField control={form.control} name="code" render={({ field }) => (
                <FormItem>
                  <FormLabel>Code</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="description" render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
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
          <Button type="submit" form="project-types-form" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
