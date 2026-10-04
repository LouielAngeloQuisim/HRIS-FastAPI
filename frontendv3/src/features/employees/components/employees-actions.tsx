import { createContext, useContext } from 'react'
import { type Employee } from '../data/schema'

type EmployeesActionsContextType = {
  onEdit?: (employee: Employee) => void
  onDelete?: (employee: Employee) => void
  deletePending?: boolean
}

export const EmployeesActionsContext =
  createContext<EmployeesActionsContextType>({})

export function EmployeesActionsProvider({
  children,
  onEdit,
  onDelete,
  deletePending,
}: {
  children: React.ReactNode
  onEdit?: (employee: Employee) => void
  onDelete?: (employee: Employee) => void
  deletePending?: boolean
}) {
  return (
    <EmployeesActionsContext.Provider value={{ onEdit, onDelete, deletePending }}>
      {children}
    </EmployeesActionsContext.Provider>
  )
}

export function useEmployeesActions() {
  return useContext(EmployeesActionsContext)
}
