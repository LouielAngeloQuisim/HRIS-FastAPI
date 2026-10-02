import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
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
import { useProjectTypes } from '@/lib/api/project-types'
import { saveErrorMessage } from '@/lib/api/save-error'
import { useCreateProject } from '@/lib/api/projects'
import { useCan } from '@/context/permissions-provider'
import { toast } from 'sonner'
import { ChevronLeft, ChevronRight, Check } from 'lucide-react'

const categorySchema = z.object({
  name: z.string().min(1, 'Category code is required').max(32),
  description: z.string().optional().nullable(),
})

const projectSchema = z.object({
  code: z.string().min(1, 'Project code is required').max(32),
  name: z.string().min(1, 'Project name is required'),
  description: z.string().optional().nullable(),
  project_type_id: z.string().optional(),
  phase_id: z.string().min(1, 'Phase is required'),

  block_id: z.string().optional(),
  lot_id: z.string().optional(),
})

type CategoryForm = z.infer<typeof categorySchema>
type ProjectForm = z.infer<typeof projectSchema>

type WizardStep = 'subdivision' | 'category' | 'project'

export function SubdivisionWizard() {
  const [step, setStep] = useState<WizardStep>('subdivision')
  const [subdivisionId, setSubdivisionId] = useState('')
  const [createdProject, setCreatedProject] = useState<{ id: string; name: string } | null>(null)
  const [projectError, setProjectError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const canView = useCan('subdivision', 'view')
  const canCreateProject = useCan('project', 'add')
  const canCreateCategory = useCan('category', 'add')

  const { data: subdivisionsData } = useSubdivisions(1, 100)
  const { data: phasesData } = usePhases(1, 100)
  const { data: blocksData } = useBlocks(1, 100)
  const { data: lotsData } = useLots(1, 100)
  const projectTypes = useProjectTypes(1, 100)
  const createCategory = useCreateCategory()
  const createProject = useCreateProject()

  const categoryForm = useForm<CategoryForm>({
    resolver: zodResolver(categorySchema),
    defaultValues: { name: '', description: '' },
  })

  const projectForm = useForm<ProjectForm>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      code: '',
      name: '',
      description: '',
      project_type_id: '',
      phase_id: '',
      block_id: '',
      lot_id: '',
    },
  })

  const subdivisions = subdivisionsData?.data ?? []
  const phases = (phasesData?.data ?? []).filter(phase => phase.subdivision_id === subdivisionId)
  const blocks = blocksData?.data ?? []
  const lots = lotsData?.data ?? []

  const selectedProjectType = useWatch({ control: projectForm.control, name: 'project_type_id' })
  const selectedLot = useWatch({ control: projectForm.control, name: 'lot_id' })
  const selectedPhase = useWatch({ control: projectForm.control, name: 'phase_id' })
  const selectedBlock = useWatch({ control: projectForm.control, name: 'block_id' })
  const filteredBlocks = blocks.filter(b => b.phase_id === selectedPhase)
  const filteredLots = lots.filter(l => l.blocks_id === selectedBlock)

  const handleSubdivisionNext = () => {
    if (!subdivisionId) {
      toast.error('Please select a subdivision')
      return
    }
    setStep('category')
  }

  const handleCategoryNext = async () => {
    if (await categoryForm.trigger()) { setProjectError(null); setStep('project') }
  }

  const handleProjectSubmit = async () => {
    if (!await projectForm.trigger()) return
    setIsSubmitting(true)
    setProjectError(null)
    try {
      const data = projectForm.getValues()
      let project = createdProject
      if (!project) {
        project = await createProject.mutateAsync({
          code: data.code, name: data.name, description: data.description ?? null,
          project_type_id: data.project_type_id || null, subdivision_id: subdivisionId,
        })
        if (!project?.id) throw new Error('Project response did not contain its ID')
        setCreatedProject(project)
      }
      const category = categoryForm.getValues()
      await createCategory.mutateAsync({
        code: category.name, description: category.description ?? null,
        project_id: project.id, phase_id: data.phase_id,
        blocks_id: data.block_id || null, lot_id: data.lot_id || null,
      })
      toast.success('Project and category created successfully')
      setStep('subdivision')
      setSubdivisionId('')
      setCreatedProject(null)
      categoryForm.reset()
      projectForm.reset()
    } catch (error) {
      setProjectError(saveErrorMessage(error))
    } finally { setIsSubmitting(false) }
  }

  if (!canView || !canCreateProject || !canCreateCategory) {
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
        <p className="text-muted-foreground">Choose a subdivision, enter the category, then create its project. Nothing is saved until the final step.</p>
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
              <SelectTrigger data-testid="wizard-subdivision-select">
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
              <Label htmlFor="wizard-category-code">Category Code</Label>
              <Input id="wizard-category-code" data-testid="wizard-category-code-input" {...categoryForm.register('name')} placeholder="Enter category name" />
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
            <Button variant="outline" onClick={() => setStep('subdivision')} disabled={Boolean(createdProject)}>
              <ChevronLeft className="mr-2 h-4 w-4" /> Back
            </Button>
            <Button onClick={handleCategoryNext} disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Next'}
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
              <Label htmlFor="wizard-project-code">Project Code</Label>
              <Input id="wizard-project-code" data-testid="wizard-project-code-input" {...projectForm.register('code')} placeholder="Enter project code" disabled={Boolean(createdProject)} />
              {projectForm.formState.errors.code && <p className="text-sm text-destructive">{projectForm.formState.errors.code.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Project Name</Label>
              <Input data-testid="wizard-project-name-input" {...projectForm.register('name')} placeholder="Enter project name" disabled={Boolean(createdProject)} />
              {projectForm.formState.errors.name && (
                <p className="text-sm text-destructive">{projectForm.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                {...projectForm.register('description')}
                disabled={Boolean(createdProject)}
                placeholder="Enter project description"
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>Project Type</Label>
              <Select
                disabled={Boolean(createdProject)}
                value={selectedProjectType}
                onValueChange={(value) => projectForm.setValue('project_type_id', value === '__none__' ? '' : value)}
              >
                <SelectTrigger data-testid="wizard-project-type-select">
                  <SelectValue placeholder="Select project type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {(projectTypes.data?.data ?? []).map(type => <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Phase</Label>
              <Select
                value={selectedPhase}
                onValueChange={(value) => {
                  projectForm.setValue('phase_id', value)
                  projectForm.setValue('block_id', '')
                  projectForm.setValue('lot_id', '')
                }}
              >
                <SelectTrigger data-testid="wizard-phase-select">
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
                value={selectedBlock}
                onValueChange={(value) => {
                  projectForm.setValue('block_id', value)
                  projectForm.setValue('lot_id', '')
                }}
                disabled={!selectedPhase}
              >
                <SelectTrigger data-testid="wizard-block-select">
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
                value={selectedLot}
                onValueChange={(value) => projectForm.setValue('lot_id', value)}
                disabled={!selectedBlock}
              >
                <SelectTrigger data-testid="wizard-lot-select">
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
          {projectError && (
            <div role="alert" className="rounded-md border p-4 space-y-2">
              {createdProject && <p>Project created: {createdProject.name}. Category still needs to be saved.</p>}
              <p className="text-destructive">{projectError}</p>
              {createdProject && <Button variant="outline" onClick={handleProjectSubmit} disabled={isSubmitting}>Retry Category</Button>}
            </div>
          )}
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep('category')} disabled={isSubmitting}>
              <ChevronLeft className="mr-2 h-4 w-4" /> Back
            </Button>
            <Button onClick={handleProjectSubmit} disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create Project & Category'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
