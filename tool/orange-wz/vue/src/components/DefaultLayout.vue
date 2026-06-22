<template>
  <el-container>
    <el-header><LayoutHeader /></el-header>
    <el-container>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
  import LayoutHeader from '@/components/LayoutHeader.vue';
</script>

<style scoped>
  .el-header {
    padding: 0;
  }
  .el-main {
    background-color: rgb(229, 233, 242);
    height: calc(100vh - 60px);
  }
</style>
