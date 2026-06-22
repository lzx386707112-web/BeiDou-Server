import DefaultLayout from '@/components/DefaultLayout.vue';
import WzEditor from '@/views/wz/WzEditor.vue';
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'wz',
      redirect: '/editor',
      component: DefaultLayout,
      children: [
        {
          path: '/editor',
          name: 'wzEditor',
          component: WzEditor,
          meta: {
            title: 'Wz编辑器',
            icon: 'GiMushroomHouse',
          },
        },
      ],
    },
  ],
});

export default router;
