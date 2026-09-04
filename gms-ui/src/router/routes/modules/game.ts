import { DEFAULT_LAYOUT } from '../base';
import { AppRouteRecordRaw } from '../types';

const GAME: AppRouteRecordRaw = {
  path: '/game',
  name: 'game',
  component: DEFAULT_LAYOUT,
  meta: {
    locale: 'menu.game',
    requiresAuth: true,
    icon: 'icon-dice',
    order: 0,
  },
  children: [
    {
      path: 'config',
      name: 'Config',
      component: () => import('@/views/game/config/index.vue'),
      meta: {
        locale: 'menu.game.config',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'setItem',
      name: 'SetItemConfig',
      component: () => import('@/views/game/setItem/index.vue'),
      meta: {
        locale: 'menu.game.setItem',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'weather',
      name: 'WeatherConfig',
      component: () => import('@/views/game/weather/index.vue'),
      meta: {
        locale: 'menu.game.weather',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'equipmentCatalog',
      name: 'EquipmentCatalog',
      component: () => import('@/views/game/equipmentCatalog/index.vue'),
      meta: {
        locale: 'menu.game.equipmentCatalog',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'cashShop',
      name: 'CashShop',
      component: () => import('@/views/game/cashShop/index.vue'),
      meta: {
        locale: 'menu.game.cashShop',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'npcShop',
      name: 'NpcShop',
      component: () => import('@/views/game/npcShop/index.vue'),
      meta: {
        locale: 'menu.game.npcShop',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'drop',
      name: 'drop',
      component: () => import('@/views/game/drop/index.vue'),
      meta: {
        locale: 'menu.game.drop',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'drop/global',
      name: 'globalDrop',
      component: () => import('@/views/game/drop/global.vue'),
      meta: {
        locale: 'menu.game.drop.global',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'inventory',
      name: 'inventory',
      component: () => import('@/views/game/inventory/index.vue'),
      meta: {
        locale: 'menu.game.inventory',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'gachapon',
      name: 'gachapon',
      component: () => import('@/views/game/gachapon/index.vue'),
      meta: {
        locale: 'menu.game.gachapon',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'operationTools',
      name: 'GameOperationTools',
      component: () => import('@/views/dashboard/operationTools/index.vue'),
      meta: {
        locale: 'menu.game.operationTools',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'commandInfo',
      name: 'commandInfo',
      component: () => import('@/views/game/commandInfo/index.vue'),
      meta: {
        locale: 'menu.game.command',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'file',
      name: 'file',
      component: () => import('@/views/game/file/index.vue'),
      meta: {
        locale: 'menu.game.file',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'autoban',
      name: 'autoban',
      component: () => import('@/views/game/autoban/index.vue'),
      meta: {
        locale: 'menu.game.autoban',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'mapDetect',
      name: 'MapDetect',
      component: () => import('@/views/game/mapDetect/index.vue'),
      meta: {
        locale: 'menu.game.mapDetect',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
    {
      path: 'questBrowse',
      name: 'QuestBrowse',
      component: () => import('@/views/game/questBrowse/index.vue'),
      meta: {
        locale: 'menu.game.questBrowse',
        requiresAuth: true,
        roles: ['admin'],
      },
    },
  ],
};

export default GAME;
