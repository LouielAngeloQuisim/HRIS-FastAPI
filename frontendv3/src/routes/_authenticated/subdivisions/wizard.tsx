import { createFileRoute } from '@tanstack/react-router'
import { SubdivisionWizardPage } from '@/features/subdivisions/components/subdivision-wizard-page'

export const Route = createFileRoute('/_authenticated/subdivisions/wizard')({
  component: SubdivisionWizardPage,
})
