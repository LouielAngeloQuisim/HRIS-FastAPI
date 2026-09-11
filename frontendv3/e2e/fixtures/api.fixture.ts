import { type APIRequestContext } from '@playwright/test'

export interface TestDataIds {
  divisionIds: string[]
  departmentIds: string[]
  subdivisionIds: string[]
  dtrIds: string[]
  leaveRequestIds: string[]
  dtrAdjustmentIds: string[]
}

export async function seedTestData(request: APIRequestContext): Promise<TestDataIds> {
  const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

  const divisionIds: string[] = []
  const departmentIds: string[] = []
  const subdivisionIds: string[] = []
  const dtrIds: string[] = []
  const leaveRequestIds: string[] = []
  const dtrAdjustmentIds: string[] = []

  for (let i = 0; i < 3; i++) {
    const divisionRes = await request.post(`${API_URL}/divisions`, {
      data: {
        code: `E2E-DIV-${Date.now()}-${i}`,
        name: `E2E Division ${i}`,
        description: 'Seeded for E2E tests',
      },
    })
    if (divisionRes.ok()) {
      const body = await divisionRes.json()
      divisionIds.push(body.data?.id || body.id)
    }
  }

  if (divisionIds.length > 0) {
    for (let i = 0; i < 2; i++) {
      const deptRes = await request.post(`${API_URL}/departments`, {
        data: {
          code: `E2E-DEPT-${Date.now()}-${i}`,
          name: `E2E Department ${i}`,
          division_id: divisionIds[0],
        },
      })
      if (deptRes.ok()) {
        const body = await deptRes.json()
        departmentIds.push(body.data?.id || body.id)
      }
    }

    if (departmentIds.length > 0) {
      for (let i = 0; i < 2; i++) {
        const subdivRes = await request.post(`${API_URL}/subdivisions`, {
          data: {
            code: `E2E-SUB-${Date.now()}-${i}`,
            name: `E2E Subdivision ${i}`,
            department_id: departmentIds[0],
          },
        })
        if (subdivRes.ok()) {
          const body = await subdivRes.json()
          subdivisionIds.push(body.data?.id || body.id)
        }
      }
    }
  }

  return {
    divisionIds,
    departmentIds,
    subdivisionIds,
    dtrIds,
    leaveRequestIds,
    dtrAdjustmentIds,
  }
}

export async function cleanupTestData(request: APIRequestContext, ids: TestDataIds): Promise<void> {
  const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

  for (const id of ids.divisionIds) {
    await request.delete(`${API_URL}/divisions/${id}`).catch(() => {})
  }
  for (const id of ids.departmentIds) {
    await request.delete(`${API_URL}/departments/${id}`).catch(() => {})
  }
  for (const id of ids.subdivisionIds) {
    await request.delete(`${API_URL}/subdivisions/${id}`).catch(() => {})
  }
  for (const id of ids.dtrIds) {
    await request.delete(`${API_URL}/daily-time-records/${id}`).catch(() => {})
  }
  for (const id of ids.leaveRequestIds) {
    await request.delete(`${API_URL}/leave-requests/${id}`).catch(() => {})
  }
  for (const id of ids.dtrAdjustmentIds) {
    await request.delete(`${API_URL}/dtr-adjustments/${id}`).catch(() => {})
  }
}
