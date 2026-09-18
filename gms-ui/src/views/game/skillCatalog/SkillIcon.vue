<template>
  <div class="skill-icon-wrapper">
    <img
      v-if="skillId"
      :key="skillId"
      :src="iconUrl"
      :alt="`技能 ${skillId}`"
      class="skill-icon"
      @error="handleError"
    />
    <div v-else class="skill-icon-placeholder">
      <icon-question />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { getSkillIconUrl, handleSkillIconError } from '@/api/skillCatalog';

  const props = defineProps<{
    skillId: number;
  }>();

  const iconUrl = computed(() => getSkillIconUrl(props.skillId));

  const handleError = (event: Event) => {
    handleSkillIconError(event, props.skillId);
  };
</script>

<style scoped lang="less">
  .skill-icon-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    flex-shrink: 0;
  }

  .skill-icon {
    width: 40px;
    height: 40px;
    object-fit: contain;
    image-rendering: pixelated;
  }

  .skill-icon-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: var(--color-fill-2);
    border-radius: 4px;
    color: var(--color-text-4);
  }
</style>
