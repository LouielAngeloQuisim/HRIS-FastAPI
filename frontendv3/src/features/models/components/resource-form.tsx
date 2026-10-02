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
import { SelectDropdown } from '@/components/select-dropdown'
import { useCreateModel, useUpdateModel } from '@/lib/api/models'
import { useModelTypes } from '@/lib/api/model-types'
import type { ModelPublic, ModelCreate, ModelUpdate } from '@/lib/api/types'

const formSchema = z.object({
  name: z.string().min(1, 'Model name is required'),
  model_type_id: z.string().optional().transform(value => value || null),
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FormData = any

interface Props {
  item: ModelPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateModel()
  const updateMutation = useUpdateModel()
  const { data: modelTypeData, isPending: modelTypesPending } = useModelTypes(1, 100)

  const modelTypeItems = modelTypeData?.data.map((mt) => ({
    label: mt.name || mt.code,
    value: mt.id,
  }))

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: item?.name ?? '',
      model_type_id: item?.model_type_id ?? '',
    },
  })

  const onSubmit = async (data: FormData) => {
    form.clearErrors('root.server')
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: data as unknown as ModelUpdate })
      } else {
        await createMutation.mutateAsync(data as unknown as ModelCreate)
      }
      onClose()
    } catch (error) {
      form.setError('root.server', { message: saveErrorMessage(error) })
    }
  }

  const loading = createMutation.isPending || updateMutation.isPending

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className="flex flex-col">
        <SheetHeader>
          <SheetTitle>{isEdit ? 'Update' : 'Create'} Model</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the model by providing necessary info.' : 'Add a new model by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="models-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            {form.formState.errors.root?.server?.message && <p role="alert" className="text-destructive">{String(form.formState.errors.root.server.message)}</p>}
            <>
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="model-name-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="model_type_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Model Type</FormLabel>
                  <FormControl>
                     <SelectDropdown
                       defaultValue={field.value}
                       onValueChange={field.onChange}
                       placeholder="Select model type"
                       items={modelTypeItems ?? []}
                       isPending={modelTypesPending}
                       data-testid="model-model-type-select"
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
          <Button type="submit" form="models-form" disabled={loading} data-testid="model-submit-button">
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
