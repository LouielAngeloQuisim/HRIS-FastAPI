import {
  Building2,
  CalendarClock,
  type LucideIcon,
  FolderKanban,
  LandPlot,
  Layers,
  Network,
  UserRound,
  Users,
  UserSquare2,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { type DashboardStats } from '@/lib/api/types'

type TileDef = {
  key: keyof DashboardStats
  label: string
  icon: LucideIcon
  hint?: string
}

// Order + labels mirror the legacy dashboard tile groups. Numbers are rendered
// verbatim from the backend — no client-side arithmetic (Q: no recompute).
const TILES: TileDef[] = [
  { key: 'employee_records', label: 'Employee Records', icon: Users },
  { key: 'divisions', label: 'Divisions', icon: Building2 },
  { key: 'departments', label: 'Departments', icon: Network },
  { key: 'projects', label: 'Projects', icon: FolderKanban },
  { key: 'subdivisions', label: 'Subdivisions', icon: LandPlot },
  { key: 'owners', label: 'Owners', icon: UserSquare2 },
  { key: 'employee_projects', label: 'Employee Projects', icon: Layers },
  { key: 'model_count', label: 'Model Count', icon: UserRound },
  {
    key: 'dtr_records_daily_count',
    label: 'Daily Time Records',
    icon: CalendarClock,
    hint: 'Attendance tracking not live yet',
  },
]

export function DashboardTiles({ data }: { data: DashboardStats }) {
  return (
    <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'>
      {TILES.map((tile) => {
        const Icon = tile.icon
        const value = data[tile.key]
        return (
          <Card key={tile.key}>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>{tile.label}</CardTitle>
              <Icon className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div
                className='text-2xl font-bold'
                data-testid={`kpi-${tile.key}`}
              >
                {value.toLocaleString()}
              </div>
              {tile.hint && (
                <p className='mt-1 text-xs text-muted-foreground'>{tile.hint}</p>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export function DashboardTilesSkeleton() {
  return (
    <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'>
      {TILES.map((tile) => (
        <Card key={tile.key}>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <Skeleton className='h-4 w-32' />
            <Skeleton className='h-4 w-4' />
          </CardHeader>
          <CardContent>
            <Skeleton className='h-7 w-20' />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
