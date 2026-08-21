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

      <div class="section-heading">
        <span>{{ $t('setItem.create.slots') }}</span>
        <a-button size="small" @click="addSlot">
          <template #icon><icon-plus /></template>
          {{ $t('setItem.action.addSlot') }}
        </a-button>
      </div>
      <div
        v-for="(slot, slotIndex) in form.slots"
        :key="slotIndex"
        class="slot-row"
      >
        <div class="slot-header">
          <span>{{ $t('setItem.slot', { index: slotIndex + 1 }) }}</span>
          <a-tooltip :content="$t('setItem.action.removeSlot')">
            <a-button
              type="text"
              status="danger"
              size="mini"
              :disabled="form.slots.length === 1"
              @click="removeSlot(slotIndex)"
            >
              <template #icon><icon-delete /></template>
            </a-button>
          </a-tooltip>
        </div>
        <div class="selected-equipment">
          <div v-for="item in slot" :key="item.id" class="equipment-item">
            <span class="equipment-image">
              <img
                :src="getEquipmentPreviewUrl(item.id)"
                :alt="item.name"
                @error="handleEquipmentPreviewError($event, item.id)"
              />
            </span>
            <span class="equipment-text">
              <strong>{{ item.name }}</strong>
              <small>{{ item.id }}</small>
            </span>
            <a-tooltip :content="$t('setItem.action.removeEquipment')">
              <a-button
                type="text"
                status="danger"
                size="mini"
                @click="removeEquipment(slotIndex, item.id)"
              >
                <template #icon><icon-close /></template>
              </a-button>
            </a-tooltip>
          </div>
          <a-button
            type="outline"
            size="small"
            @click="openEquipmentSearch(slotIndex)"
          >
            <template #icon><icon-search /></template>
            {{ $t('setItem.action.addEquipment') }}
          </a-button>
        </div>
      </div>

      <div class="section-heading tier-heading">
        <span>{{ $t('setItem.create.tiers') }}</span>
        <a-button size="small" @click="addTier">
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
              {{ $t(`setItem.stat.${option}`) }}
            </a-option>
          </a-select>
          <a-input-number
            v-model="stat.value"
            :min="0"
            :max="statMaximum(stat.key)"
            :precision="0"
            :style="{ width: '180px' }"
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
        <a-button type="text" size="small" @click="addStat(tierIndex)">
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

  <a-modal
    v-model:visible="searchVisible"
    :width="'min(720px, calc(100vw - 32px))'"
    :title="$t('setItem.equipmentSearch.title')"
    :footer="false"
    unmount-on-close
  >
    <a-space class="search-toolbar">
      <a-input
        v-model="searchKeyword"
        allow-clear
        :placeholder="$t('setItem.equipmentSearch.placeholder')"
        @press-enter="runEquipmentSearch"
      >
        <template #prefix><icon-search /></template>
      </a-input>
      <a-button type="primary" :loading="searching" @click="runEquipmentSearch">
        <template #icon><icon-search /></template>
        {{ $t('setItem.action.search') }}
      </a-button>
    </a-space>
    <a-table
      row-key="id"
      :data="searchResults"
      :loading="searching"
      :pagination="false"
      :scroll="{ y: 420 }"
    >
      <template #columns>
        <a-table-column
          :title="$t('setItem.column.preview')"
          :width="76"
          align="center"
        >
          <template #cell="{ record }">
            <a-popover
              position="right"
              trigger="hover"
              :content-style="{ padding: 0, background: 'transparent' }"
            >
              <EquipmentIcon compact :item-id="record.id" :alt="record.name" />
              <template #content>
                <EquipmentTooltip :item="record" />
              </template>
            </a-popover>
          </template>
        </a-table-column>
        <a-table-column
          :title="$t('setItem.column.itemId')"
          data-index="id"
          :width="120"
        />
        <a-table-column
          :title="$t('setItem.column.itemName')"
          data-index="name"
        />
        <a-table-column
          :title="$t('setItem.column.operation')"
          :width="90"
          align="center"
        >
          <template #cell="{ record }">
            <a-button type="text" size="small" @click="selectEquipment(record)">
              <template #icon><icon-plus /></template>
              {{ $t('setItem.action.select') }}
            </a-button>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
  import { reactive, ref } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { useI18n } from 'vue-i18n';
  import {
    createSetItem,
    SET_ITEM_STAT_KEYS,
    SetItemDefinitionCreate,
    SetItemEquipment,
  } from '@/api/setItem';
  import {
    EquipmentCatalogItem,
    getEquipmentCatalog,
  } from '@/api/equipmentCatalog';
  import {
    getEquipmentPreviewUrl,
    handleEquipmentPreviewError,
  } from '@/utils/mapleStoryAPI';
  import EquipmentIcon from '@/views/game/equipmentCatalog/EquipmentIcon.vue';
  import EquipmentTooltip from '@/views/game/equipmentCatalog/EquipmentTooltip.vue';

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
  const searchVisible = ref(false);
  const searching = ref(false);
  const searchKeyword = ref('');
  const searchResults = ref<EquipmentCatalogItem[]>([]);
  const targetSlot = ref(0);
  const jobOptions = [-1, 0, 1, 2, 3, 4];
  const statOptions = SET_ITEM_STAT_KEYS;
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
    searchKeyword.value = '';
    searchResults.value = [];
  };

  const open = () => {
    reset();
    visible.value = true;
  };

  const addSlot = () => form.slots.push([]);

  const removeSlot = (index: number) => {
    form.slots.splice(index, 1);
    form.tiers.forEach((tier) => {
      tier.requiredCount = Math.min(tier.requiredCount, form.slots.length);
    });
  };

  const openEquipmentSearch = (slotIndex: number) => {
    targetSlot.value = slotIndex;
    searchKeyword.value = '';
    searchResults.value = [];
    searchVisible.value = true;
  };

  const runEquipmentSearch = async () => {
    if (!searchKeyword.value.trim()) return;
    searching.value = true;
    try {
      const { data } = await getEquipmentCatalog({
        keyword: searchKeyword.value.trim(),
        pageNo: 1,
        pageSize: 30,
      });
      searchResults.value = data.records;
    } finally {
      searching.value = false;
    }
  };

  const selectEquipment = (item: EquipmentCatalogItem) => {
    if (form.slots.some((slot) => slot.some((entry) => entry.id === item.id))) {
      Message.warning(t('setItem.validation.duplicateEquipment'));
      return;
    }
    form.slots[targetSlot.value].push(item);
    searchVisible.value = false;
  };

  const removeEquipment = (slotIndex: number, itemId: number) => {
    form.slots[slotIndex] = form.slots[slotIndex].filter(
      (item) => item.id !== itemId
    );
  };

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

  const statMaximum = (stat: string) => {
    const normalized = stat.toLowerCase();
    return normalized.endsWith('rate') ||
      ['finaldamage', 'bossdamage'].includes(normalized)
      ? 10000
      : 1000000;
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
  .slot-header,
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

  .slot-row,
  .tier-row {
    padding: 12px 0;
    border-top: 1px solid var(--color-border-2);
  }

  .slot-header {
    margin-bottom: 8px;
    color: var(--color-text-2);
  }

  .selected-equipment {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .equipment-item {
    display: flex;
    max-width: 260px;
    min-height: 42px;
    align-items: center;
    gap: 8px;
    padding: 4px 4px 4px 6px;
    border: 1px solid var(--color-border-2);
    border-radius: 4px;
  }

  .equipment-image {
    display: inline-flex;
    width: 38px;
    height: 38px;
    flex: 0 0 38px;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: var(--color-fill-2);
    border-radius: 4px;
  }

  .equipment-image img {
    max-width: 34px;
    max-height: 34px;
    object-fit: contain;
  }

  .equipment-text {
    display: flex;
    min-width: 0;
    flex-direction: column;
  }

  .equipment-text strong {
    overflow: hidden;
    font-size: 13px;
    font-weight: 500;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .equipment-text small {
    color: var(--color-text-3);
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

  .search-toolbar {
    display: flex;
    width: 100%;
    margin-bottom: 16px;
  }

  .search-toolbar :deep(.arco-input-wrapper) {
    flex: 1;
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
