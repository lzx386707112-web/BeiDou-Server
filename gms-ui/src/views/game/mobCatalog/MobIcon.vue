<template>
  <span class="mob-icon" :class="{ compact }">
    <img
      :src="getMobPreviewUrl(mobId)"
      :alt="alt"
      @error="handleMobPreviewError($event, mobId)"
    />
  </span>
</template>

<script setup lang="ts">
  import { getMobPreviewUrl, handleMobPreviewError } from '@/api/mobCatalog';

  defineProps<{
    mobId: number;
    alt: string;
    compact?: boolean;
  }>();
</script>

<style scoped lang="less">
  .mob-icon {
    display: inline-flex;
    width: 56px;
    height: 56px;
    flex: 0 0 56px;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border: 1px solid var(--color-neutral-3);
    border-radius: 6px;
    background: var(--color-fill-2);

    &.compact {
      width: 44px;
      height: 44px;
      flex-basis: 44px;
    }

    img {
      display: block;
      width: 48px;
      height: 48px;
      object-fit: contain;
      image-rendering: auto;
    }

    &.compact img {
      width: 40px;
      height: 40px;
    }
  }
</style>
