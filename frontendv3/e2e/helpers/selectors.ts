export const Selectors = {
  addButton: (resource: string) => `[data-testid="add-${resource}-button"]`,
  editButton: (resource: string, index = 0) => `[data-testid^="edit-${resource}-button"]:nth(${index + 1})`,
  deleteButton: (resource: string, index = 0) => `[data-testid^="delete-${resource}-button"]:nth(${index + 1})`,
  confirmDialog: {
    confirm: () => '[data-testid="confirm-delete-button"]',
    cancel: () => '[data-testid="cancel-delete-button"]',
  },
  table: () => '[role="table"], table',
  row: (index: number) => `[role="row"]:nth(${index + 1}), table tbody tr:nth(${index + 1})`,
  retry: () => '[data-testid="retry-button"]',
  statusFilter: (name: string) => `[data-testid="${name}"]`,
}
