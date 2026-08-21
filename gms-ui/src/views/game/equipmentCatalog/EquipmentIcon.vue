<template>
  <span class="equipment-icon" :class="{ compact }">
    <img
      :src="getEquipmentPreviewUrl(itemId)"
      :alt="alt"
      @error="handleEquipmentPreviewError($event, itemId)"
    />
  </span>
</template>

<script setup lang="ts">
  import {
    getEquipmentPreviewUrl,
    handleEquipmentPreviewError,
  } from '@/utils/mapleStoryAPI';

  withDefaults(
    defineProps<{
      itemId: number;
      alt: string;
      compact?: boolean;
    }>(),
    { compact: false }
  );
</script>

<style scoped lang="less">
  .equipment-icon {
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
