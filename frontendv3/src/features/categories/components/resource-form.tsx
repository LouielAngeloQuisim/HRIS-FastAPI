import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { SelectDropdown } from '@/components/select-dropdown'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { useCreateCategory, useUpdateCategory } from '@/lib/api/categories'
import { useProjects } from '@/lib/api/projects'
import { usePhases } from '@/lib/api/phases'
import { useBlocks } from '@/lib/api/blocks'
import { useLots } from '@/lib/api/lots'
import { useModels } from '@/lib/api/models'
import { useOwners } from '@/lib/api/owners'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { CategoryPublic } from '@/lib/api/types'

const formSchema = z.object({
  code: z.string().min(1, 'Category code is required').max(32),
  description: z.string().max(1024).optional(),
  location: z.string().max(255).optional(),
  is_overhead: z.boolean(),
  project_id: z.string().min(1, 'Select a project'),
  phase_id: z.string().min(1, 'Select a phase'),
  blocks_id: z.string().optional(),
  lot_id: z.string().optional(),
  model_id: z.string().optional(),
  owner_id: z.string().optional(),
})
type FormData = z.infer<typeof formSchema>
interface Props { item: CategoryPublic | null; onClose: () => void; open: boolean }

export function ResourceForm({ item, onClose, open }: Props) {
  const create = useCreateCategory()
  const update = useUpdateCategory()
  const projects = useProjects(1, 100)
  const phases = usePhases(1, 100)
  const blocks = useBlocks(1, 100)
  const lots = useLots(1, 100)
  const models = useModels(1, 100)
  const owners = useOwners(1, 100)
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      code: item?.code ?? '', description: item?.description ?? '', location: item?.location ?? '',
      is_overhead: item?.is_overhead ?? false, project_id: item?.project_id ?? '', phase_id: item?.phase_id ?? '',
      blocks_id: item?.blocks_id ?? '', lot_id: item?.lot_id ?? '', model_id: item?.model_id ?? '', owner_id: item?.owner_id ?? '',
    },
  })
  const selectedProject = projects.data?.data.find(project => project.id === form.watch('project_id'))
  const selectedPhase = form.watch('phase_id')
  const selectedBlock = form.watch('blocks_id')
  const relations = [
    { name: 'project_id', label: 'Project', pending: projects.isPending, items: projects.data?.data.map(value => ({ value: value.id, label: value.name })), required: true },
    { name: 'phase_id', label: 'Phase', pending: phases.isPending, items: phases.data?.data.filter(value => value.subdivision_id === selectedProject?.subdivision_id).map(value => ({ value: value.id, label: value.name })), required: true },
    { name: 'blocks_id', label: 'Block', pending: blocks.isPending, items: blocks.data?.data.filter(value => value.phase_id === selectedPhase).map(value => ({ value: value.id, label: value.block_name })) },
    { name: 'lot_id', label: 'Lot', pending: lots.isPending, items: lots.data?.data.filter(value => value.blocks_id === selectedBlock).map(value => ({ value: value.id, label: value.lot_name || String(value.lot_num) })) },
    { name: 'model_id', label: 'Model', pending: models.isPending, items: models.data?.data.map(value => ({ value: value.id, label: value.name })) },
    { name: 'owner_id', label: 'Owner', pending: owners.isPending, items: owners.data?.data.map(value => ({ value: value.id, label: [value.first_name, value.last_name].filter(Boolean).join(' ') })) },
  ] as const
  const onSubmit = async (data: FormData) => {
    form.clearErrors('root.server')
    const payload = { ...data, blocks_id: data.blocks_id || null, lot_id: data.lot_id || null, model_id: data.model_id || null, owner_id: data.owner_id || null }
    try {
      if (item) await update.mutateAsync({ id: item.id, data: payload })
      else await create.mutateAsync(payload)
      onClose()
    } catch (error) { form.setError('root.server', { message: saveErrorMessage(error) }) }
  }
  return (
    <Sheet open={open} onOpenChange={value => { if (!value) onClose() }}>
      <SheetContent className="flex flex-col">
        <SheetHeader><SheetTitle>{item ? 'Update' : 'Create'} Category</SheetTitle><SheetDescription>Provide the category and its project relationships.</SheetDescription></SheetHeader>
        <Form {...form}>
          <form id="categories-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-4 overflow-y-auto px-4">
            {form.formState.errors.root?.server?.message && <p role="alert" className="text-destructive">{form.formState.errors.root.server.message}</p>}
            {(['code', 'description', 'location'] as const).map(name => (
              <FormField key={name} control={form.control} name={name} render={({ field }) => (
                <FormItem><FormLabel>{name === 'code' ? 'Code' : name === 'description' ? 'Description' : 'Location'}</FormLabel><FormControl><Input {...field} value={field.value ?? ''} data-testid={'category-' + name + '-input'} /></FormControl><FormMessage /></FormItem>
              )} />
            ))}
            {relations.map(relation => (
              <FormField key={relation.name} control={form.control} name={relation.name} render={({ field }) => (
                <FormItem><FormLabel>{relation.label}</FormLabel><SelectDropdown defaultValue={field.value || '__none__'} isControlled onValueChange={value => {
                  field.onChange(value === '__none__' ? '' : value)
                  if (relation.name === 'project_id') { form.setValue('phase_id', ''); form.setValue('blocks_id', ''); form.setValue('lot_id', '') }
                  if (relation.name === 'phase_id') { form.setValue('blocks_id', ''); form.setValue('lot_id', '') }
                  if (relation.name === 'blocks_id') form.setValue('lot_id', '')
                }} items={'required' in relation && relation.required ? relation.items : [{ value: '__none__', label: 'None' }, ...(relation.items ?? [])]} placeholder={'Select ' + relation.label.toLowerCase()} isPending={relation.pending} data-testid={'category-' + relation.name.replace('_id', '') + '-select'} /><FormMessage /></FormItem>
              )} />
            ))}
            <FormField control={form.control} name="is_overhead" render={({ field }) => (
              <FormItem><FormLabel>Overhead</FormLabel><FormControl><Switch checked={field.value} onCheckedChange={field.onChange} data-testid="category-overhead-switch" /></FormControl><FormMessage /></FormItem>
            )} />
          </form>
        </Form>
        <SheetFooter><SheetClose asChild><Button type="button" variant="outline">Cancel</Button></SheetClose><Button type="submit" form="categories-form" disabled={create.isPending || update.isPending} data-testid="category-submit-button">{item ? 'Update' : 'Create'}</Button></SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
