import { DEFAULT_LAYOUT } from '../base';
import { AppRouteRecordRaw } from '../types';

const DASHBOARD: AppRouteRecordRaw = {
  path: '/dashboard',
  name: 'dashboard',
  component: DEFAULT_LAYOUT,
  meta: {
    locale: 'menu.dashboard',
    requiresAuth: true,
    icon: 'icon-dashboard',
    order: 0,
  },
  children: [
    {
      path: 'workplace',
      name: 'Workplace',
      component: () => import('@/views/dashboard/workplace/index.vue'),
      meta: {
        locale: 'menu.dashboard.workplace',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'operationTools',
      name: 'OperationTools',
      component: () => import('@/views/dashboard/operationTools/index.vue'),
      meta: {
        locale: 'menu.dashboard.operationTools',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'informationSearch',
      name: 'informationSearch',
      component: () => import('@/views/dashboard/informationSearch/index.vue'),
      meta: {
        locale: 'menu.dashboard.informationSearch',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
  ],
};

export default DASHBOARD;
