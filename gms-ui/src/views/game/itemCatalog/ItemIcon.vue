<template>
  <span class="item-icon" :class="{ compact }">
    <img
      :src="getItemPreviewUrl(itemId)"
      :alt="alt"
      @error="handleItemPreviewError($event, itemId)"
    />
  </span>
</template>

<script setup lang="ts">
  import { getItemPreviewUrl, handleItemPreviewError } from '@/api/itemCatalog';

  defineProps<{
    itemId: number;
    alt: string;
    compact?: boolean;
  }>();
</script>

<style scoped lang="less">
  .item-icon {
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
