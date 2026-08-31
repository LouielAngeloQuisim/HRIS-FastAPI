import { SubdivisionWizard } from './subdivision-wizard'

export function SubdivisionWizardPage() {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
          <SubdivisionWizard />
        </div>
      </div>
    </div>
  )
}
