import {
  LayoutDashboard,
  Users,
  CalendarClock,
  Building2,
  Network,
  LandPlot,
  UserCog,
  Clock,
  FolderKanban,
  ListTree,
  Blocks,
  Home,
  Tags,
  GitBranch,
  UserRound,
  ClipboardList,
  ShieldCheck,
} from 'lucide-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  user: {
    name: 'HRIS User',
    email: 'user@hris.local',
    avatar: '/avatars/01.png',
  },
  teams: [
    {
      name: 'HRIS',
      logo: LayoutDashboard,
      plan: 'Human Resource Information System',
    },
  ],
  navGroups: [
    {
      title: 'General',
      items: [
        {
          title: 'Dashboard',
          url: '/',
          icon: LayoutDashboard,
        },
      ],
    },
    {
      title: 'Human Resource',
      items: [
        {
          title: 'Employees',
          url: '/employees',
          icon: Users,
          permission: { module: 'emp_list' },
        },
        {
          title: 'Daily Time Records',
          url: '/daily-time-records',
          icon: CalendarClock,
          permission: { module: 'daily_time_record' },
        },
      ],
    },
    {
      title: 'Organization',
      items: [
        {
          title: 'Divisions',
          url: '/divisions',
          icon: Building2,
          permission: { module: 'division' },
        },
        {
          title: 'Departments',
          url: '/departments',
          icon: Network,
          permission: { module: 'department' },
        },
        {
          title: 'Subdivisions',
          url: '/subdivisions',
          icon: LandPlot,
          permission: { module: 'subdivision' },
        },
        {
          title: 'Positions',
          url: '/positions',
          icon: UserCog,
          permission: { module: 'position' },
        },
      ],
    },
    {
      title: 'Projects',
      items: [
        {
          title: 'Projects',
          url: '/projects',
          icon: FolderKanban,
          permission: { module: 'projects' },
        },
        {
          title: 'Phases',
          url: '/phases',
          icon: ListTree,
          permission: { module: 'phase' },
        },
        {
          title: 'Blocks',
          url: '/blocks',
          icon: Blocks,
          permission: { module: 'blocks' },
        },
        {
          title: 'Lots',
          url: '/lots',
          icon: Home,
          permission: { module: 'lots' },
        },
        {
          title: 'Categories',
          url: '/categories',
          icon: Tags,
          permission: { module: 'category' },
        },
        {
          title: 'Models',
          url: '/models',
          icon: GitBranch,
          permission: { module: 'models' },
        },
        {
          title: 'Model Types',
          url: '/model-types',
          icon: ClipboardList,
          permission: { module: 'model_types' },
        },
        {
          title: 'Owners',
          url: '/owners',
          icon: UserRound,
          permission: { module: 'owner' },
        },
      ],
    },
    {
      title: 'Employee Management',
      items: [
        {
          title: 'Employee Projects',
          url: '/employee-projects',
          icon: FolderKanban,
          permission: { module: 'emp_project' },
        },
        {
          title: 'Emp Tasks',
          url: '/emp-tasks',
          icon: ClipboardList,
          permission: { module: 'emp_task' },
        },
      ],
    },
    {
      title: 'Administration',
      items: [
        {
          title: 'Roles',
          url: '/roles',
          icon: ShieldCheck,
          permission: { module: 'administration' },
        },
        {
          title: 'Shifts',
          url: '/shifts',
          icon: Clock,
          permission: { module: 'shifts' },
        },
      ],
    },
  ],
}