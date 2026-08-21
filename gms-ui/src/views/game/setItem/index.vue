<template>
  <div class="container">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('menu.game.setItem')">
      <a-space class="toolbar" wrap>
        <a-button type="primary" @click="createModal?.open()">
          <template #icon><icon-plus /></template>
          {{ $t('setItem.action.create') }}
        </a-button>
        <a-input
          v-model="keyword"
          allow-clear
          :placeholder="$t('setItem.filter.placeholder')"
          :style="{ width: '240px' }"
        >
          <template #prefix><icon-search /></template>
        </a-input>
        <a-select v-model="jobFilter" :style="{ width: '160px' }">
          <a-option :value="99">{{ $t('setItem.filter.allJobs') }}</a-option>
          <a-option v-for="job in jobOptions" :key="job" :value="job">
            {{ jobName(job) }}
          </a-option>
        </a-select>
        <a-tooltip :content="$t('setItem.action.refresh')">
          <a-button :loading="loading" @click="loadCatalog">
            <template #icon><icon-refresh /></template>
          </a-button>
        </a-tooltip>
      </a-space>

      <a-table
        row-key="id"
        :loading="loading"
        :data="filteredCatalog"
        :bordered="{ cell: true }"
        :scroll="{ x: 1180 }"
        :pagination="{ pageSize: 20, showTotal: true, showJumper: true }"
      >
        <template #columns>
          <a-table-column
            :title="$t('setItem.column.id')"
            data-index="id"
            :width="95"
            align="center"
          />
          <a-table-column :title="$t('setItem.column.equipment')" :width="230">
            <template #cell="{ record }">
              <div class="equipment-preview">
                <a-tooltip
                  v-for="item in previewEquipment(record)"
                  :key="item.id"
                  :content="`${item.name} (${item.id})`"
                >
                  <span class="equipment-icon">
                    <img
                      :src="getEquipmentPreviewUrl(item.id)"
                      :alt="item.name"
                      @error="handleEquipmentPreviewError($event, item.id)"
                    />
                  </span>
                </a-tooltip>
                <span class="slot-count">
                  {{ $t('setItem.slotCount', { count: record.slots.length }) }}
                </span>
              </div>
            </template>
          </a-table-column>
          <a-table-column
            :title="$t('setItem.column.name')"
            data-index="name"
            :width="210"
          />
          <a-table-column
            :title="$t('setItem.column.job')"
            :width="110"
            align="center"
          >
            <template #cell="{ record }">
              <a-tag>{{ jobName(record.jobIndex) }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column
            :title="$t('setItem.column.completeCount')"
            data-index="completeCount"
            :width="105"
            align="center"
          />
          <a-table-column :title="$t('setItem.column.tiers')" :width="230">
            <template #cell="{ record }">
              <a-space wrap>
                <a-tag v-for="tier in record.tiers" :key="tier.requiredCount">
                  {{ $t('setItem.tier', { count: tier.requiredCount }) }}
                </a-tag>
              </a-space>
            </template>
          </a-table-column>
          <a-table-column
            :title="$t('setItem.column.status')"
            :width="100"
            align="center"
          >
            <template #cell="{ record }">
              <a-tag v-if="!record.enabled" color="gray">
                {{ $t('setItem.status.disabled') }}
              </a-tag>
              <a-tag v-else-if="!record.builtIn" color="arcoblue">
                {{ $t('setItem.status.custom') }}
              </a-tag>
              <a-tag v-else-if="isCustomized(record)" color="orangered">
                {{ $t('setItem.status.customized') }}
              </a-tag>
              <a-tag v-else color="green">
                {{ $t('setItem.status.default') }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column
            :title="$t('setItem.column.operation')"
            :width="310"
            align="center"
            fixed="right"
          >
            <template #cell="{ record }">
              <a-space>
                <a-button
                  type="text"
                  size="mini"
                  :disabled="!record.enabled"
                  @click="openEditor(record)"
                >
                  <template #icon><icon-edit /></template>
                  {{ $t('setItem.action.edit') }}
                </a-button>
                <a-popconfirm
                  :content="$t('setItem.reset.confirm')"
                  @ok="resetDefinition(record)"
                >
                  <a-button
                    type="text"
                    status="danger"
                    size="mini"
                    :disabled="!record.enabled || !isCustomized(record)"
                  >
                    <template #icon><icon-undo /></template>
                    {{ $t('setItem.action.reset') }}
                  </a-button>
                </a-popconfirm>
                <a-popconfirm
                  v-if="record.builtIn"
                  :content="
                    record.enabled
                      ? $t('setItem.disable.confirm')
                      : $t('setItem.enable.confirm')
                  "
                  @ok="toggleBuiltIn(record)"
                >
                  <a-button
                    type="text"
                    size="mini"
                    :status="record.enabled ? 'danger' : 'success'"
                  >
                    <template #icon>
                      <icon-pause v-if="record.enabled" />
                      <icon-play-arrow v-else />
                    </template>
                    {{
                      record.enabled
                        ? $t('setItem.action.disable')
                        : $t('setItem.action.enable')
                    }}
                  </a-button>
                </a-popconfirm>
                <a-popconfirm
                  v-else
                  :content="$t('setItem.delete.confirm')"
                  @ok="deleteDefinition(record)"
                >
                  <a-button type="text" status="danger" size="mini">
                    <template #icon><icon-delete /></template>
                    {{ $t('setItem.action.delete') }}
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:visible="editorVisible"
      :width="'min(760px, calc(100vw - 32px))'"
      :title="editorTitle"
      :footer="false"
      unmount-on-close
    >
      <a-tabs v-if="editing" v-model:active-key="activeTier">
        <a-tab-pane
          v-for="tier in editing.tiers"
          :key="String(tier.requiredCount)"
          :title="$t('setItem.tier', { count: tier.requiredCount })"
        >
          <a-row :gutter="16">
            <a-col
              v-for="stat in Object.keys(editValues[tier.requiredCount] || {})"
              :key="stat"
              :xs="24"
              :sm="12"
            >
              <a-form-item :label="$t(`setItem.stat.${stat}`)">
                <div class="stat-editor-control">
                  <a-input-number
                    v-model="editValues[tier.requiredCount][stat]"
                    :min="0"
                    :max="statMaximum(stat)"
                    :step="1"
                    :precision="0"
                    hide-button
                  />
                  <a-tooltip :content="$t('setItem.action.removeStat')">
                    <a-button
                      type="text"
                      status="danger"
                      size="mini"
                      @click="removeEditorStat(tier.requiredCount, stat)"
                    >
                      <template #icon><icon-close /></template>
                    </a-button>
                  </a-tooltip>
                </div>
                <span v-if="stat in tier.defaultStats" class="default-value">
                  {{
                    $t('setItem.defaultValue', {
                      value: tier.defaultStats[stat],
                    })
                  }}
                </span>
                <span v-else class="default-value">
                  {{ $t('setItem.newStat') }}
                </span>
              </a-form-item>
            </a-col>
          </a-row>
          <a-space v-if="availableEditorStats(tier.requiredCount).length">
            <a-select
              v-model="newStats[tier.requiredCount]"
              :placeholder="$t('setItem.action.addStat')"
              :style="{ width: '220px' }"
            >
              <a-option
                v-for="stat in availableEditorStats(tier.requiredCount)"
                :key="stat"
                :value="stat"
              >
                {{ $t(`setItem.stat.${stat}`) }}
              </a-option>
            </a-select>
            <a-button
              type="outline"
              :disabled="!newStats[tier.requiredCount]"
              @click="addEditorStat(tier.requiredCount)"
            >
              <template #icon><icon-plus /></template>
              {{ $t('setItem.action.addStat') }}
            </a-button>
          </a-space>
        </a-tab-pane>
      </a-tabs>
      <a-divider />
      <div class="modal-actions">
        <a-button @click="fillDefaults">
          <template #icon><icon-undo /></template>
          {{ $t('setItem.action.localReset') }}
        </a-button>
        <a-space>
          <a-button @click="editorVisible = false">
            {{ $t('setItem.action.cancel') }}
          </a-button>
          <a-button type="primary" :loading="saving" @click="saveDefinition">
            <template #icon><icon-save /></template>
            {{ $t('setItem.action.save') }}
          </a-button>
        </a-space>
      </div>
    </a-modal>
    <SetItemCreateModal ref="createModal" @created="loadCatalog" />
  </div>
</template>

<script setup lang="ts">
  import { computed, reactive, ref } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { useI18n } from 'vue-i18n';
  import useLoading from '@/hooks/loading';
  import {
    getSetItemCatalog,
    deleteCustomSetItem,
    resetSetItem,
    SET_ITEM_STAT_KEYS,
    SetItemDefinition,
    SetItemEquipment,
    setBuiltInSetItemEnabled,
    updateSetItem,
  } from '@/api/setItem';
  import {
    getEquipmentPreviewUrl,
    handleEquipmentPreviewError,
  } from '@/utils/mapleStoryAPI';
  import SetItemCreateModal from './SetItemCreateModal.vue';

  const { t } = useI18n();
  const { loading, setLoading } = useLoading(false);
  const catalog = ref<SetItemDefinition[]>([]);
  const keyword = ref('');
  const jobFilter = ref(99);
  const jobOptions = [-1, 0, 1, 2, 3, 4];
  const editorVisible = ref(false);
  const saving = ref(false);
  const editing = ref<SetItemDefinition>();
  const activeTier = ref('');
  const editValues = reactive<Record<number, Record<string, number>>>({});
  const newStats = reactive<Record<number, string | undefined>>({});
  const createModal = ref<InstanceType<typeof SetItemCreateModal>>();

  const filteredCatalog = computed(() => {
    const search = keyword.value.trim().toLowerCase();
    return catalog.value.filter((definition) => {
      const jobMatches =
        jobFilter.value === 99 || definition.jobIndex === jobFilter.value;
      const textMatches =
        !search ||
        definition.name.toLowerCase().includes(search) ||
        String(definition.id).includes(search);
      return jobMatches && textMatches;
    });
  });

  const editorTitle = computed(() => {
    if (!editing.value) return '';
    return `${editing.value.name} · ${jobName(editing.value.jobIndex)} · ${
      editing.value.id
    }`;
  });

  const jobName = (jobIndex: number) => {
    const keys = ['warrior', 'magician', 'bowman', 'thief', 'pirate'];
    return jobIndex < 0
      ? t('setItem.job.shared')
      : t(`setItem.job.${keys[jobIndex]}`);
  };

  const isCustomized = (definition: SetItemDefinition) =>
    definition.tiers.some((tier) => tier.customized);

  const previewEquipment = (definition: SetItemDefinition) => {
    const result: SetItemEquipment[] = [];
    definition.slots.forEach((slot) => {
      if (slot[0]) result.push(slot[0]);
    });
    return result.slice(0, 6);
  };

  const statMaximum = (stat: string) => {
    const normalized = stat.toLowerCase();
    const rateStats = [
      'finaldamage',
      'bossdamage',
      'statusres',
      'buffduration',
    ];
    return normalized.endsWith('rate') ||
      normalized.endsWith('pct') ||
      rateStats.includes(normalized)
      ? 10000
      : 1000000;
  };

  const loadCatalog = async () => {
    setLoading(true);
    try {
      const { data } = await getSetItemCatalog();
      catalog.value = data;
    } finally {
      setLoading(false);
    }
  };

  const openEditor = (definition: SetItemDefinition) => {
    if (!definition.enabled) return;
    editing.value = definition;
    Object.keys(editValues).forEach((key) => delete editValues[Number(key)]);
    Object.keys(newStats).forEach((key) => delete newStats[Number(key)]);
    definition.tiers.forEach((tier) => {
      editValues[tier.requiredCount] = { ...tier.stats };
    });
    activeTier.value = String(definition.tiers[0]?.requiredCount ?? '');
    editorVisible.value = true;
  };

  const fillDefaults = () => {
    editing.value?.tiers.forEach((tier) => {
      editValues[tier.requiredCount] = { ...tier.defaultStats };
    });
  };

  const availableEditorStats = (requiredCount: number) =>
    SET_ITEM_STAT_KEYS.filter(
      (stat) => !(stat in (editValues[requiredCount] || {}))
    );

  const addEditorStat = (requiredCount: number) => {
    const stat = newStats[requiredCount];
    if (!stat) return;
    const tier = editing.value?.tiers.find(
      (entry) => entry.requiredCount === requiredCount
    );
    editValues[requiredCount][stat] = tier?.defaultStats[stat] ?? 0;
    newStats[requiredCount] = undefined;
  };

  const removeEditorStat = (requiredCount: number, stat: string) => {
    delete editValues[requiredCount][stat];
  };

  const saveDefinition = async () => {
    if (!editing.value) return;
    saving.value = true;
    try {
      const { data } = await updateSetItem(editing.value.id, editValues);
      Message.success(t('setItem.save.success', { count: data }));
      editorVisible.value = false;
      await loadCatalog();
    } finally {
      saving.value = false;
    }
  };

  const resetDefinition = async (definition: SetItemDefinition) => {
    const { data } = await resetSetItem(definition.id);
    Message.success(t('setItem.reset.success', { count: data }));
    await loadCatalog();
  };

  const toggleBuiltIn = async (definition: SetItemDefinition) => {
    const { data } = await setBuiltInSetItemEnabled(
      definition.id,
      !definition.enabled
    );
    Message.success(
      t(
        definition.enabled
          ? 'setItem.disable.success'
          : 'setItem.enable.success',
        { count: data }
      )
    );
    await loadCatalog();
  };

  const deleteDefinition = async (definition: SetItemDefinition) => {
    const { data } = await deleteCustomSetItem(definition.id);
    Message.success(t('setItem.delete.success', { count: data }));
    await loadCatalog();
  };

  loadCatalog();
</script>

<script lang="ts">
  export default {
    name: 'SetItemConfig',
  };
</script>

<style scoped lang="less">
  .toolbar {
    margin-bottom: 16px;
  }

  .default-value {
    margin-left: 8px;
    color: var(--color-text-3);
    white-space: nowrap;
  }

  .stat-editor-control {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .equipment-preview {
    display: flex;
    min-height: 36px;
    align-items: center;
    gap: 4px;
  }

  .equipment-icon {
    display: inline-flex;
    width: 34px;
    height: 34px;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border: 1px solid var(--color-border-2);
    background: var(--color-fill-2);
    border-radius: 4px;
  }

  .equipment-icon img {
    max-width: 30px;
    max-height: 30px;
    object-fit: contain;
  }

  .slot-count {
    margin-left: 4px;
    color: var(--color-text-3);
    white-space: nowrap;
  }

  .modal-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  @media (max-width: 575px) {
    .modal-actions {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
