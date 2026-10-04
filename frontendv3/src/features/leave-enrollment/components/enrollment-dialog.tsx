import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useEnrollEmployee } from '@/lib/api/leave-policies'
import { useEmployees } from '@/lib/api/employees'
import { toast } from 'sonner'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { LeavePolicyPublic } from '@/lib/api/types'

type EnrollmentDialogProps = {
  open: boolean
  _onOpenChange: (open: boolean) => void
  employeeId: string | undefined
  leaveYear: number
  availablePolicies: LeavePolicyPublic[]
  onClose: () => void
}

export function EnrollmentDialog({
  open,
  _onOpenChange,
  employeeId,
  leaveYear,
  availablePolicies,
  onClose,
}: EnrollmentDialogProps) {
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | undefined>(employeeId)
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | undefined>(undefined)
  const [selectedYear, setSelectedYear] = useState<number>(leaveYear)
  const createMutation = useEnrollEmployee()
  const loading = createMutation.isPending

  const { data: employeesData } = useEmployees(1, 500)
  const employees = employeesData?.data ?? []
  const selectedEmployee = employees.find((e) => e.id === selectedEmployeeId)

  const handleEnroll = async () => {
    if (!selectedEmployeeId || !selectedPolicyId) return
    try {
      await createMutation.mutateAsync({
        employee_id: selectedEmployeeId,
        data: { policy_id: selectedPolicyId, leave_year: selectedYear },
      })
      toast.success('Employee enrolled in leave policy')
      setSelectedPolicyId(undefined)
      onClose()
    } catch (error) {
      toast.error(saveErrorMessage(error))
    }
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className='flex flex-col'>
        <SheetHeader>
          <SheetTitle>Enroll Employee in Leave Policy</SheetTitle>
          <SheetDescription>
            {selectedEmployee
              ? `Enroll ${selectedEmployee.first_name} ${selectedEmployee.last_name} in a leave policy for ${selectedYear}.`
              : 'Select an employee and a leave policy to enroll them.'}
          </SheetDescription>
        </SheetHeader>
        <div className='flex-1 space-y-4 px-4 py-6'>
          <div className='space-y-2'>
            <label htmlFor='enrollment-employee-select' className='text-sm font-medium'>Employee</label>
            <Select value={selectedEmployeeId} onValueChange={setSelectedEmployeeId}>
              <SelectTrigger id='enrollment-employee-select' data-testid='enrollment-dialog-employee-select'>
                <SelectValue placeholder='Select employee' />
              </SelectTrigger>
              <SelectContent>
                {employees.map((emp) => (
                  <SelectItem key={emp.id} value={emp.id}>
                    {emp.employee_code} — {emp.first_name} {emp.last_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <label htmlFor='enrollment-policy-select' className='text-sm font-medium'>Leave Policy</label>
            <Select value={selectedPolicyId} onValueChange={setSelectedPolicyId}>
              <SelectTrigger id='enrollment-policy-select' data-testid='enrollment-dialog-policy-select'>
                <SelectValue placeholder='Select leave policy' />
              </SelectTrigger>
              <SelectContent>
                {availablePolicies.map((policy) => (
                  <SelectItem key={policy.id} value={policy.id}>
                    {policy.code} — {policy.name} ({policy.annual_entitlement_days ?? '0.00'} days)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <label htmlFor='enrollment-year-select' className='text-sm font-medium'>Leave Year</label>
            <Select value={selectedYear.toString()} onValueChange={(v) => setSelectedYear(Number(v))}>
              <SelectTrigger id='enrollment-year-select' data-testid='enrollment-dialog-year-select'>
                <SelectValue placeholder='Select leave year' />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 10 }, (_, i) => {
                  const year = new Date().getFullYear() - 5 + i
                  return <SelectItem key={year} value={year.toString()}>{year}</SelectItem>
                })}
              </SelectContent>
            </Select>
          </div>
        </div>
        <SheetFooter className='gap-2'>
          <SheetClose asChild>
            <Button type='button' variant='outline'>Cancel</Button>
          </SheetClose>
          <Button onClick={handleEnroll} disabled={loading || !employeeId || !selectedPolicyId} data-testid='enrollment-dialog-submit-button'>
            {loading ? 'Enrolling...' : 'Enroll'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
