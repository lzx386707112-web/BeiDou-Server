<template>
  <div class="header">
    <el-menu
      :default-active="defaultActive"
      router
      mode="horizontal"
      background-color="#545c64"
      text-color="#fff"
      active-text-color="#ffd04b"
    >
      <el-menu-item index="/">
        <img style="width: 48px; height: 48px" :src="logo" alt="蘑菇物语" />
      </el-menu-item>
      <template v-for="item in routerMenu" :key="item.name">
        <el-menu-item
          v-if="item.children?.length == 0 || item.children == undefined"
          :index="item.path"
        >
          <template #title>
            <component :is="getIcon(item.meta?.icon)" :width="18" :height="18" />
            <span style="margin-left: 5px">{{ item?.meta?.title }}</span>
          </template>
        </el-menu-item>

        <el-sub-menu v-else :index="item.name">
          <template #title>
            <component :is="getIcon(item.meta?.icon)" :width="18" :height="18" />
            <span style="margin-left: 5px">{{ item?.meta?.title }}</span>
          </template>
          <template v-for="subItem in item.children" :key="subItem.name">
            <el-menu-item :index="subItem.path">
              <template #title>
                <component :is="getIcon(subItem.meta?.icon)" :width="18" :height="18" />
                <span style="margin-left: 5px">{{ subItem?.meta?.title }}</span>
              </template>
            </el-menu-item>
          </template>
        </el-sub-menu>
      </template>
      <el-menu-item @click="openUrl('https://moguwuyu.com')">
        <template #title>
          <component :is="getIcon('AiOutlineComment')" :width="18" :height="18" />
          <span style="margin-left: 5px">蘑菇物语</span>
        </template>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
  import logo from '@/assets/logo.png';
  import { ref } from 'vue';
  import { type RouteRecordRaw, useRouter } from 'vue-router';

  /* Icon ------------------------------------------------------------------------------------------------------------*/
  import { AiOutlineComment, AiOutlineHome } from 'vue-icons-plus/ai';
  import { GiMushroomHouse } from 'vue-icons-plus/gi';
  const iconComponents = {
    AiOutlineHome: AiOutlineHome,
    GiMushroomHouse: GiMushroomHouse,
    AiOutlineComment: AiOutlineComment,
  };
  const getIcon = (icon: string | undefined) => {
    if (icon === undefined) return;
    return iconComponents[icon as keyof typeof iconComponents];
  };

  const defaultActive = ref<string>('');
  const routerMenu = ref<RouteRecordRaw[]>([]);
  const initial = () => {
    const router = useRouter();
    defaultActive.value = router.currentRoute.value.path?.toString() || '';
    const routes = router.options.routes;
    routes.forEach((route) => {
      if (route.meta && route.meta.hideInMenu) return;

      const c = ref<RouteRecordRaw[]>([]);
      if (route.children) {
        route.children.forEach((child) => {
          c.value.push(child);
        });
      }

      if (c.value.length == 1) {
        routerMenu.value.push(c.value[0]);
        return;
      }

      route.children = c.value;
      routerMenu.value.push(route);
    });
  };
  initial();

  const openUrl = (url: string | undefined) => {
    if (url === undefined) return;
    window.open(url);
  };
</script>

<style scoped>
  .header {
    background-color: #545c64;
  }
</style>
