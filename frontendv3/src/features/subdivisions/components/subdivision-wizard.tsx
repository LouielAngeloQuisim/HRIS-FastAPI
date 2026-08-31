import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useSubdivisions } from '@/lib/api/subdivisions'
import { usePhases } from '@/lib/api/phases'
import { useBlocks } from '@/lib/api/blocks'
import { useLots } from '@/lib/api/lots'
import { useCreateCategory } from '@/lib/api/categories'
import type { CategoryCreate, ProjectCreate } from '@/lib/api/types'
import { useCreateProject } from '@/lib/api/projects'
import { useCan } from '@/context/permissions-provider'
import { toast } from 'sonner'
import { ChevronLeft, ChevronRight, Check } from 'lucide-react'

const categorySchema = z.object({
  name: z.string().min(1, 'Category name is required'),
  description: z.string().optional().nullable(),
})

const projectSchema = z.object({
  name: z.string().min(1, 'Project name is required'),
  description: z.string().optional().nullable(),
  project_type_id: z.string().min(1, 'Project type is required'),
  phase_id: z.string().min(1, 'Phase is required'),

  block_id: z.string().min(1, 'Block is required'),
  lot_id: z.string().min(1, 'Lot is required'),
})

type CategoryForm = z.infer<typeof categorySchema>
type ProjectForm = z.infer<typeof projectSchema>

type WizardStep = 'subdivision' | 'category' | 'project'

export function SubdivisionWizard() {
  const [step, setStep] = useState<WizardStep>('subdivision')
  const [subdivisionId, setSubdivisionId] = useState('')
  const [createdCategory, setCreatedCategory] = useState<{ id: string; code: string } | null>(null)
  const [projectError, setProjectError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const canView = useCan('subdivision', 'view')

  const { data: subdivisionsData } = useSubdivisions(1, 100)
  const { data: phasesData } = usePhases(1, 100)
  const { data: blocksData } = useBlocks(1, 100)
  const { data: lotsData } = useLots(1, 100)
  const createCategory = useCreateCategory()
  const createProject = useCreateProject()

  const categoryForm = useForm<CategoryForm>({
    resolver: zodResolver(categorySchema),
    defaultValues: { name: '', description: '' },
  })

  const projectForm = useForm<ProjectForm>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: '',
      description: '',
      project_type_id: '',
      phase_id: '',
      block_id: '',
      lot_id: '',
    },
  })

  const subdivisions = subdivisionsData?.data ?? []
  const phases = phasesData?.data ?? []
  const blocks = blocksData?.data ?? []
  const lots = lotsData?.data ?? []

  // Filter blocks by selected phase
  const filteredBlocks = blocks.filter(b => b.phase_id === projectForm.watch('phase_id'))
  // Filter lots by selected block
  const filteredLots = lots.filter(l => l.blocks_id === projectForm.watch('block_id'))

  const handleSubdivisionNext = () => {
    if (!subdivisionId) {
      toast.error('Please select a subdivision')
      return
    }
    setStep('category')
  }

  const handleCategoryNext = async () => {
    const valid = await categoryForm.trigger()
    if (!valid) return

    setIsSubmitting(true)
    try {
      const categoryData = categoryForm.getValues()
      const created = await createCategory.mutateAsync({
        code: categoryData.name,
        description: categoryData.description ?? null,
      } as unknown as CategoryCreate)
      const createdId = (created as { id?: string; code?: string })?.id ?? null
      const createdCode = (created as { id?: string; code?: string })?.code ?? categoryData.name
      setCreatedCategory(createdId ? { id: createdId, code: createdCode } : null)
      toast.success('Category created successfully')
      setProjectError(null)
      setStep('project')
    } catch {
      toast.error('Failed to create category')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleProjectSubmit = async () => {
    const valid = await projectForm.trigger()
    if (!valid) return

    setIsSubmitting(true)
    try {
      const projectData = projectForm.getValues()
      await createProject.mutateAsync({
        name: projectData.name,
        description: projectData.description ?? null,
        project_type_id: projectData.project_type_id,
        subdivision_id: subdivisionId,
      } as unknown as ProjectCreate)
      toast.success('Project created successfully')
      // Reset wizard
      setStep('subdivision')
      setSubdivisionId('')
      setCreatedCategory(null)
      setProjectError(null)
      categoryForm.reset()
      projectForm.reset()
    } catch (err) {
      const resp = (err as { response?: { data?: { error?: { message?: string }; detail?: string | string[] } } })?.response?.data
      const msg =
        resp?.error?.message ??
        (Array.isArray(resp?.detail) ? resp?.detail[0] : resp?.detail) ??
        'Failed to create project'
      setProjectError(msg)
      toast.error('Failed to create project')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to access the subdivision wizard.</p>
      </div>
    )
  }

  const steps = [
    { id: 'subdivision', label: 'Subdivision Details', number: 1 },
    { id: 'category', label: 'Category Details', number: 2 },
    { id: 'project', label: 'Project Details', number: 3 },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Subdivision Wizard</h1>
        <p className="text-muted-foreground">Create a new project by selecting subdivision, adding category, and configuring project details.</p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-between">
        {steps.map((s, idx) => (
          <div key={s.id} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step === s.id
                  ? 'bg-primary text-primary-foreground'
                  : steps.findIndex(st => st.id === step) > idx
                    ? 'bg-green-500 text-white'
                    : 'bg-muted text-muted-foreground'
              }`}
            >
              {steps.findIndex(st => st.id === step) > idx ? <Check className="h-4 w-4" /> : s.number}
            </div>
            <span className={`text-sm ${step === s.id ? 'font-medium' : 'text-muted-foreground'}`}>
              {s.label}
            </span>
            {idx < steps.length - 1 && <div className="mx-4 h-px w-12 bg-muted" />}
          </div>
        ))}
      </div>

      {/* Step 1: Subdivision Selection */}
      {step === 'subdivision' && (
        <div className="space-y-4 rounded-lg border p-6">
          <h3 className="text-lg font-medium">Subdivision Details</h3>
          <div className="space-y-2">
            <Label>Select Subdivision</Label>
            <Select value={subdivisionId} onValueChange={setSubdivisionId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a subdivision" />
              </SelectTrigger>
              <SelectContent>
                {subdivisions.map(sub => (
                  <SelectItem key={sub.id} value={sub.id}>
                    {sub.subdivision_code} - {sub.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end">
            <Button onClick={handleSubdivisionNext} disabled={!subdivisionId}>
              Next <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Category Creation */}
      {step === 'category' && (
        <div className="space-y-4 rounded-lg border p-6">
          <h3 className="text-lg font-medium">Category Details</h3>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Category Name</Label>
              <Input {...categoryForm.register('name')} placeholder="Enter category name" />
              {categoryForm.formState.errors.name && (
                <p className="text-sm text-destructive">{categoryForm.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                {...categoryForm.register('description')}
                placeholder="Enter category description"
                rows={3}
              />
            </div>
          </div>
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep('subdivision')}>
              <ChevronLeft className="mr-2 h-4 w-4" /> Back
            </Button>
            <Button onClick={handleCategoryNext} disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create Category & Next'}
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Project Creation */}
      {step === 'project' && (
        <div className="space-y-4 rounded-lg border p-6">
          <h3 className="text-lg font-medium">Project Details</h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Project Name</Label>
              <Input {...projectForm.register('name')} placeholder="Enter project name" />
              {projectForm.formState.errors.name && (
                <p className="text-sm text-destructive">{projectForm.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                {...projectForm.register('description')}
                placeholder="Enter project description"
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>Project Type</Label>
              <Select
                value={projectForm.watch('project_type_id')}
                onValueChange={(value) => projectForm.setValue('project_type_id', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select project type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pt-1">Residential</SelectItem>
                  <SelectItem value="pt-2">Commercial</SelectItem>
                  <SelectItem value="pt-3">Industrial</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Phase</Label>
              <Select
                value={projectForm.watch('phase_id')}
                onValueChange={(value) => {
                  projectForm.setValue('phase_id', value)
                  projectForm.setValue('block_id', '')
                  projectForm.setValue('lot_id', '')
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select phase" />
                </SelectTrigger>
                <SelectContent>
                  {phases.map(phase => (
                    <SelectItem key={phase.id} value={phase.id}>
                      {phase.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Block</Label>
              <Select
                value={projectForm.watch('block_id')}
                onValueChange={(value) => {
                  projectForm.setValue('block_id', value)
                  projectForm.setValue('lot_id', '')
                }}
                disabled={!projectForm.watch('phase_id')}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select block" />
                </SelectTrigger>
                <SelectContent>
                  {filteredBlocks.map(block => (
                    <SelectItem key={block.id} value={block.id}>
                      {block.block_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Lot</Label>
              <Select
                value={projectForm.watch('lot_id')}
                onValueChange={(value) => projectForm.setValue('lot_id', value)}
                disabled={!projectForm.watch('block_id')}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select lot" />
                </SelectTrigger>
                <SelectContent>
                  {filteredLots.map(lot => (
                    <SelectItem key={lot.id} value={lot.id}>
                      {lot.lot_name ?? String(lot.lot_num)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {createdCategory && projectError && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-4 space-y-2">
              <p className="text-sm font-medium">Partial success — category step complete</p>
              <p className="text-sm">
                Category created: <span className="font-medium">{createdCategory.code}</span>
              </p>
              <p className="text-sm text-destructive">Project failed: {projectError}</p>
              <Button variant="outline" onClick={handleProjectSubmit} disabled={isSubmitting}>
                {isSubmitting ? 'Retrying...' : 'Retry Project'}
              </Button>
            </div>
          )}
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep('category')}>
              <ChevronLeft className="mr-2 h-4 w-4" /> Back
            </Button>
            <Button onClick={handleProjectSubmit} disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
