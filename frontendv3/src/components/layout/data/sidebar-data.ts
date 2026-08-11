import {
  LayoutDashboard,
  Users,
  CalendarClock,
  Building2,
  Network,
  LandPlot,
  UserCog,
  Clock,
  BookUser,
  CalendarDays,
  Send,
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
          title: 'Daily Time Records',
          url: '/daily-time-records',
          icon: CalendarClock,
          permission: { module: 'daily_time_record' },
        },
        {
          title: 'Employees',
          url: '/employees',
          icon: Users,
          permission: { module: 'emp_list' },
        },
      ],
    },
    {
      title: 'Administration',
      items: [
        {
          title: 'Division',
          url: '/division',
          icon: Building2,
          permission: { module: 'division' },
        },
        {
          title: 'Department',
          url: '/department',
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
          title: 'Employee Settings',
          url: '/employee-settings',
          icon: UserCog,
          permission: { module: 'emp_settings' },
        },
        {
          title: 'Shifts',
          url: '/shifts',
          icon: Clock,
          permission: { module: 'shifts' },
        },
      ],
    },
    {
      title: 'Leave Administration',
      items: [
        {
          title: 'Employee Leaves',
          url: '/employee-leaves',
          icon: BookUser,
          permission: { module: 'employee_leaves' },
        },
        {
          title: 'Leave Request',
          url: '/leave-request',
          icon: Send,
          permission: { module: 'leave_request' },
        },
        {
          title: 'Leave Calendar',
          url: '/leave-calendar',
          icon: CalendarDays,
          permission: { module: 'leave_calendar' },
        },
      ],
    },
  ],
}
