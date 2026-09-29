<template>
  <a-modal
    v-model:visible="visible"
    :width="'min(940px, calc(100vw - 32px))'"
    :title="$t('setItem.create.title')"
    :footer="false"
    unmount-on-close
  >
    <a-form :model="form" layout="vertical">
      <a-row :gutter="16">
        <a-col :xs="24" :sm="16">
          <a-form-item :label="$t('setItem.create.name')" required>
            <a-input v-model="form.name" :max-length="64" show-word-limit />
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="8">
          <a-form-item :label="$t('setItem.create.job')" required>
            <a-select v-model="form.jobIndex">
              <a-option v-for="job in jobOptions" :key="job" :value="job">
                {{ jobName(job) }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <SetItemSlotEditor v-model="form.slots" :minimum-slots="minimumSlots" />

      <div class="section-heading tier-heading">
        <span>{{ $t('setItem.create.tiers') }}</span>
        <a-button
          size="small"
          :disabled="form.tiers.length >= 8"
          @click="addTier"
        >
          <template #icon><icon-plus /></template>
          {{ $t('setItem.action.addTier') }}
        </a-button>
      </div>
      <div
        v-for="(tier, tierIndex) in form.tiers"
        :key="tierIndex"
        class="tier-row"
      >
        <div class="tier-toolbar">
          <a-form-item :label="$t('setItem.create.requiredCount')">
            <a-input-number
              v-model="tier.requiredCount"
              :min="1"
              :max="Math.max(1, form.slots.length)"
              :precision="0"
            />
          </a-form-item>
          <a-tooltip :content="$t('setItem.action.removeTier')">
            <a-button
              type="text"
              status="danger"
              :disabled="form.tiers.length === 1"
              @click="removeTier(tierIndex)"
            >
              <template #icon><icon-delete /></template>
            </a-button>
          </a-tooltip>
        </div>
        <div
          v-for="(stat, statIndex) in tier.stats"
          :key="statIndex"
          class="stat-row"
        >
          <a-select v-model="stat.key" :style="{ width: '220px' }">
            <a-option
              v-for="option in statOptions"
              :key="option"
              :value="option"
              :disabled="
                tier.stats.some(
                  (entry, index) => index !== statIndex && entry.key === option
                )
              "
            >
              {{ $t(`setItem.stat.${setItemStatBase(option)}`)
              }}{{
                setItemStatIsPercent(option) && option.endsWith('Pct')
                  ? ' (%)'
                  : ''
              }}
            </a-option>
          </a-select>
          <SetItemStatValue
            v-model="stat.value"
            :stat-key="stat.key"
            :disabled-keys="
              tier.stats
                .filter((_, i) => i !== statIndex)
                .map((entry) => entry.key)
            "
            @update:stat-key="changeDraftStat(stat, $event)"
          />
          <a-tooltip :content="$t('setItem.action.removeStat')">
            <a-button
              type="text"
              status="danger"
              :disabled="tier.stats.length === 1"
              @click="removeStat(tierIndex, statIndex)"
            >
              <template #icon><icon-close /></template>
            </a-button>
          </a-tooltip>
        </div>
        <a-button
          type="text"
          size="small"
          :disabled="tier.stats.length >= 24"
          @click="addStat(tierIndex)"
        >
          <template #icon><icon-plus /></template>
          {{ $t('setItem.action.addStat') }}
        </a-button>
      </div>

      <div class="modal-actions">
        <a-button @click="visible = false">{{
          $t('setItem.action.cancel')
        }}</a-button>
        <a-button type="primary" :loading="saving" @click="submit">
          <template #icon><icon-save /></template>
          {{ $t('setItem.action.create') }}
        </a-button>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
  import { computed, reactive, ref } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { useI18n } from 'vue-i18n';
  import {
    createSetItem,
    SET_ITEM_STAT_KEYS,
    SET_ITEM_PERCENT_BASES,
    setItemStatBase,
    setItemStatIsPercent,
    setItemStatMaximum,
    SetItemDefinitionCreate,
    SetItemEquipment,
  } from '@/api/setItem';
  import SetItemSlotEditor from './SetItemSlotEditor.vue';
  import SetItemStatValue from './SetItemStatValue.vue';

  interface StatDraft {
    key: string;
    value: number;
  }

  interface TierDraft {
    requiredCount: number;
    stats: StatDraft[];
  }

  interface FormState {
    name: string;
    jobIndex: number;
    slots: SetItemEquipment[][];
    tiers: TierDraft[];
  }

  const emit = defineEmits<{ (event: 'created'): void }>();
  const { t } = useI18n();
  const visible = ref(false);
  const saving = ref(false);
  const jobOptions = [-1, 0, 1, 2, 3, 4];
  const statOptions = [
    ...SET_ITEM_STAT_KEYS,
    ...SET_ITEM_PERCENT_BASES.map((key) => `${key}Pct`),
  ];
  const form = reactive<FormState>({
    name: '',
    jobIndex: -1,
    slots: [[]],
    tiers: [{ requiredCount: 1, stats: [{ key: 'PAD', value: 1 }] }],
  });

  const jobName = (jobIndex: number) => {
    const keys = ['warrior', 'magician', 'bowman', 'thief', 'pirate'];
    return jobIndex < 0
      ? t('setItem.job.shared')
      : t(`setItem.job.${keys[jobIndex]}`);
  };

  const reset = () => {
    form.name = '';
    form.jobIndex = -1;
    form.slots = [[]];
    form.tiers = [{ requiredCount: 1, stats: [{ key: 'PAD', value: 1 }] }];
  };

  const open = () => {
    reset();
    visible.value = true;
  };

  const minimumSlots = computed(() =>
    Math.max(1, ...form.tiers.map((tier) => tier.requiredCount))
  );

  const addTier = () => {
    const previous = form.tiers[form.tiers.length - 1]?.requiredCount ?? 0;
    form.tiers.push({
      requiredCount: Math.min(form.slots.length, previous + 1),
      stats: [{ key: 'PAD', value: 1 }],
    });
  };

  const removeTier = (index: number) => form.tiers.splice(index, 1);

  const addStat = (tierIndex: number) => {
    const used = new Set(form.tiers[tierIndex].stats.map((stat) => stat.key));
    const key = statOptions.find((option) => !used.has(option));
    if (!key) return;
    form.tiers[tierIndex].stats.push({ key, value: 1 });
  };

  const removeStat = (tierIndex: number, statIndex: number) => {
    form.tiers[tierIndex].stats.splice(statIndex, 1);
  };

  const changeDraftStat = (stat: StatDraft, key: string) => {
    stat.key = key;
    stat.value = Math.min(stat.value, setItemStatMaximum(key));
  };

  const submit = async () => {
    if (!form.name.trim()) {
      Message.warning(t('setItem.validation.nameRequired'));
      return;
    }
    if (form.slots.some((slot) => slot.length === 0)) {
      Message.warning(t('setItem.validation.emptySlot'));
      return;
    }
    const tierCounts = new Set(form.tiers.map((tier) => tier.requiredCount));
    if (tierCounts.size !== form.tiers.length) {
      Message.warning(t('setItem.validation.duplicateTier'));
      return;
    }
    const tiers: Record<number, Record<string, number>> = {};
    form.tiers.forEach((tier) => {
      tiers[tier.requiredCount] = {};
      tier.stats.forEach((stat) => {
        tiers[tier.requiredCount][stat.key] = stat.value;
      });
    });
    const request: SetItemDefinitionCreate = {
      name: form.name.trim(),
      jobIndex: form.jobIndex,
      slots: form.slots.map((slot) => slot.map((item) => item.id)),
      tiers,
    };
    saving.value = true;
    try {
      const { data } = await createSetItem(request);
      Message.success(t('setItem.create.success', { id: data }));
      visible.value = false;
      emit('created');
    } finally {
      saving.value = false;
    }
  };

  defineExpose({ open });
</script>

<style scoped lang="less">
  .section-heading,
  .tier-toolbar,
  .modal-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .section-heading {
    margin-bottom: 10px;
    font-size: 15px;
    font-weight: 600;
  }

  .tier-heading {
    margin-top: 24px;
  }

  .tier-row {
    padding: 12px 0;
    border-top: 1px solid var(--color-border-2);
  }

  .tier-toolbar {
    align-items: flex-start;
  }

  .stat-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .modal-actions {
    margin-top: 24px;
    justify-content: flex-end;
  }

  @media (max-width: 575px) {
    .stat-row {
      align-items: stretch;
      flex-direction: column;
    }

    .stat-row :deep(.arco-select-view),
    .stat-row :deep(.arco-input-wrapper) {
      width: 100% !important;
    }
  }
</style>
