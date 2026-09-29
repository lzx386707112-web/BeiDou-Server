<template>
  <div class="stat-value">
    <a-radio-group
      v-if="canSwitch"
      type="button"
      size="small"
      :model-value="percent"
      @change="changeMode"
    >
      <a-radio :value="false" :disabled="disabledKeys.includes(base)">
        {{ $t('setItem.value.flat') }}
      </a-radio>
      <a-radio :value="true" :disabled="disabledKeys.includes(`${base}Pct`)">
        {{ $t('setItem.value.percent') }}
      </a-radio>
    </a-radio-group>
    <a-input-number
      :model-value="modelValue"
      :min="0"
      :max="setItemStatMaximum(statKey)"
      :precision="0"
      @update:model-value="$emit('update:modelValue', $event ?? 0)"
    >
      <template v-if="percent" #suffix>%</template>
    </a-input-number>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import {
    SET_ITEM_PERCENT_BASES,
    setItemStatBase,
    setItemStatIsPercent,
    setItemStatMaximum,
  } from '@/api/setItem';

  const props = withDefaults(
    defineProps<{
      statKey: string;
      modelValue: number;
      disabledKeys?: string[];
    }>(),
    { disabledKeys: () => [] }
  );
  const emit = defineEmits<{
    (event: 'update:modelValue', value: number): void;
    (event: 'update:statKey', key: string): void;
  }>();
  const base = computed(() => setItemStatBase(props.statKey));
  const percent = computed(() => setItemStatIsPercent(props.statKey));
  const canSwitch = computed(() =>
    SET_ITEM_PERCENT_BASES.some((key) => key === base.value)
  );
  const changeMode = (value: string | number | boolean) => {
    const key = value ? `${base.value}Pct` : base.value;
    emit('update:statKey', key);
  };
</script>

<style scoped lang="less">
  .stat-value {
    display: flex;
    min-width: 0;
    flex: 1;
    flex-wrap: wrap;
    gap: 6px;
    :deep(.arco-radio-group) {
      flex-shrink: 0;
      white-space: nowrap;
    }
    .arco-input-number {
      width: 130px;
      flex: 1;
      min-width: 100px;
    }
  }
</style>
