import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useCreateRole, useUpdateRole } from '@/lib/api/roles'
import type { RolePublic, RoleCreate, RoleUpdate } from '@/lib/api/types'

const formSchema = z.object({
  name: z.string().min(1, 'Role name is required'),
})

type FormData = z.infer<typeof formSchema>

interface Props {
  open: boolean
  role: RolePublic | null
  onClose: () => void
}

export function RoleForm({ open, role, onClose }: Props) {
  const isEdit = Boolean(role?.id)
  const createMutation = useCreateRole()
  const updateMutation = useUpdateRole()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: role?.name ?? '',
    },
  })

  useEffect(() => {
    form.reset({ name: role?.name ?? '' })
  }, [role, form])

  const onSubmit = async (data: FormData) => {
    try {
      if (isEdit && role?.id) {
        await updateMutation.mutateAsync({ id: role.id, data: data as unknown as RoleUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as RoleCreate)
      }
      onClose()
    } catch {
      // mutation handles toast
    }
  }

  const loading = createMutation.isPending || updateMutation.isPending

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className="flex flex-col">
        <SheetHeader>
          <SheetTitle>{isEdit ? 'Update' : 'Create'} Role</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the role by providing necessary info.' : 'Add a new role by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="roles-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input {...field} value={field.value ?? ''} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>
        <SheetFooter>
          <SheetClose asChild>
            <Button type="button" variant="outline">Cancel</Button>
          </SheetClose>
          <Button type="submit" form="roles-form" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
