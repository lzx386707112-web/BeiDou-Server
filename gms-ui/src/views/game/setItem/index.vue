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
        :data="filteredSeries"
        :bordered="{ cell: true }"
        :scroll="{ x: 1260 }"
        :pagination="{ pageSize: 20, showTotal: true, showJumper: true }"
      >
        <template #columns>
          <a-table-column
            :title="$t('setItem.column.series')"
            data-index="name"
            :width="210"
          />
          <a-table-column
            :title="$t('setItem.column.setCount')"
            data-index="memberCount"
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
            :title="$t('setItem.column.job')"
            :width="110"
            align="center"
          >
            <template #cell="{ record }">
              <a-space wrap>
                <a-tag v-for="job in record.jobs" :key="job">{{
                  jobName(job)
                }}</a-tag>
              </a-space>
            </template>
          </a-table-column>
          <a-table-column
            :title="$t('setItem.column.completeCount')"
            data-index="completeCounts"
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
              <a-tag v-if="record.enabledCount === 0" color="gray">
                {{ $t('setItem.status.disabled') }}
              </a-tag>
              <a-tag
                v-else-if="record.enabledCount !== record.memberCount"
                color="orange"
              >
                {{ $t('setItem.status.partiallyEnabled') }}
              </a-tag>
              <a-tag v-else-if="record.mixedBonuses" color="orange">
                {{ $t('setItem.status.mixedBonuses') }}
              </a-tag>
              <a-tag v-else-if="!record.builtIn" color="arcoblue">
                {{ $t('setItem.status.custom') }}
              </a-tag>
              <a-tag
                v-else-if="record.members.some(isCustomized)"
                color="orangered"
              >
                {{ $t('setItem.status.customized') }}
              </a-tag>
              <a-tag v-else color="green">
                {{ $t('setItem.status.default') }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column
            :title="$t('setItem.column.operation')"
            :width="180"
            align="center"
            :fixed="appStore.hideMenu ? undefined : 'right'"
          >
            <template #cell="{ record }">
              <a-space>
                <a-button
                  type="text"
                  size="mini"
                  :disabled="!record.editable"
                  @click="openSeriesEditor(record)"
                >
                  <template #icon><icon-edit /></template>
                  {{ $t('setItem.action.editSeries') }}
                </a-button>
                <a-button
                  type="text"
                  size="mini"
                  @click="detailKey = record.seriesKey"
                >
                  <template #icon><icon-list /></template>
                  {{ $t('setItem.action.details') }}
                </a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <a-modal
      :visible="!!detailSeries"
      :width="'min(1000px, calc(100vw - 32px))'"
      :title="detailSeries?.name"
      :footer="false"
      @cancel="detailKey = undefined"
    >
      <a-table
        :data="detailSeries?.members || []"
        row-key="id"
        :scroll="{ x: 780 }"
        :pagination="false"
      >
        <template #columns>
          <a-table-column
            :title="$t('setItem.column.id')"
            data-index="id"
            :width="90"
          />
          <a-table-column :title="$t('setItem.column.job')" :width="100">
            <template #cell="{ record }">{{
              jobName(record.jobIndex)
            }}</template>
          </a-table-column>
          <a-table-column :title="$t('setItem.column.equipment')" :width="240">
            <template #cell="{ record }">
              <div class="equipment-preview">
                <a-tooltip
                  v-for="item in previewEquipment(record)"
                  :key="item.id"
                  :content="`${item.name} (${item.id})`"
                >
                  <span class="equipment-icon"
                    ><img
                      :src="getEquipmentPreviewUrl(item.id)"
                      :alt="item.name"
                      @error="handleEquipmentPreviewError($event, item.id)"
                  /></span>
                </a-tooltip>
              </div>
              {{ $t('setItem.slotCount', { count: record.slots.length }) }}
            </template>
          </a-table-column>
          <a-table-column :title="$t('setItem.column.status')" :width="100">
            <template #cell="{ record }">{{
              $t(
                record.enabled
                  ? 'setItem.status.default'
                  : 'setItem.status.disabled'
              )
            }}</template>
          </a-table-column>
          <a-table-column :title="$t('setItem.column.operation')" :width="310">
            <template #cell="{ record }">
              <a-space wrap>
                <a-button
                  type="text"
                  size="mini"
                  :disabled="!record.enabled"
                  @click="openEditor(record)"
                  ><template #icon><icon-edit /></template
                  >{{ $t('setItem.action.edit') }}</a-button
                >
                <a-popconfirm
                  :content="$t('setItem.reset.confirm')"
                  @ok="resetDefinition(record)"
                >
                  <a-button
                    type="text"
                    size="mini"
                    :disabled="!isCustomized(record)"
                    ><template #icon><icon-undo /></template
                    >{{ $t('setItem.action.reset') }}</a-button
                  >
                </a-popconfirm>
                <a-popconfirm
                  v-if="record.builtIn"
                  :content="
                    $t(
                      record.enabled
                        ? 'setItem.disable.confirm'
                        : 'setItem.enable.confirm'
                    )
                  "
                  @ok="toggleBuiltIn(record)"
                >
                  <a-button
                    type="text"
                    size="mini"
                    :status="record.enabled ? 'danger' : 'success'"
                    ><template #icon
                      ><icon-pause v-if="record.enabled" /><icon-play-arrow
                        v-else /></template
                    >{{
                      $t(
                        record.enabled
                          ? 'setItem.action.disable'
                          : 'setItem.action.enable'
                      )
                    }}</a-button
                  >
                </a-popconfirm>
                <a-popconfirm
                  v-else
                  :content="$t('setItem.delete.confirm')"
                  @ok="deleteDefinition(record)"
                >
                  <a-button type="text" status="danger" size="mini"
                    ><template #icon><icon-delete /></template
                    >{{ $t('setItem.action.delete') }}</a-button
                  >
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-modal>

    <a-modal
      v-model:visible="editorVisible"
      :width="'min(960px, calc(100vw - 32px))'"
      :title="editorTitle"
      :footer="false"
      unmount-on-close
    >
      <SetItemSlotEditor
        v-if="editing && !seriesEditing"
        v-model="editSlots"
        :minimum-slots="minimumSlots"
      />
      <a-alert v-if="seriesEditing" type="warning" class="series-warning">{{
        $t('setItem.series.confirm', { count: seriesMemberCount })
      }}</a-alert>
      <a-divider />
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
              <a-form-item
                class="stat-form-item"
                :label="$t(`setItem.stat.${setItemStatBase(stat)}`)"
              >
                <div class="stat-editor-field">
                  <div class="stat-editor-control">
                    <SetItemStatValue
                      v-model="editValues[tier.requiredCount][stat]"
                      :stat-key="stat"
                      :disabled-keys="
                        Object.keys(editValues[tier.requiredCount]).filter(
                          (key) => key !== stat
                        )
                      "
                      @update:stat-key="
                        changeEditorStat(tier.requiredCount, stat, $event)
                      "
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
                </div>
              </a-form-item>
            </a-col>
          </a-row>
          <a-space v-if="availableEditorStats(tier.requiredCount).length" wrap>
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
                {{ $t(`setItem.stat.${setItemStatBase(stat)}`)
                }}{{ stat.endsWith('Pct') ? ' (%)' : '' }}
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
  import { useAppStore } from '@/store';
  import {
    getSetItemCatalog,
    deleteCustomSetItem,
    resetSetItem,
    SET_ITEM_STAT_KEYS,
    SET_ITEM_PERCENT_BASES,
    setItemStatBase,
    setItemStatMaximum,
    SetItemDefinition,
    SetItemEquipment,
    setBuiltInSetItemEnabled,
    updateSetItem,
    updateSetItemSeries,
  } from '@/api/setItem';
  import {
    getEquipmentPreviewUrl,
    handleEquipmentPreviewError,
  } from '@/utils/mapleStoryAPI';
  import SetItemCreateModal from './SetItemCreateModal.vue';
  import SetItemSlotEditor from './SetItemSlotEditor.vue';
  import SetItemStatValue from './SetItemStatValue.vue';

  const { t } = useI18n();
  const appStore = useAppStore();
  const { loading, setLoading } = useLoading(false);
  const catalog = ref<SetItemDefinition[]>([]);
  const keyword = ref('');
  const jobFilter = ref(99);
  const jobOptions = [-1, 0, 1, 2, 3, 4];
  const editorVisible = ref(false);
  const saving = ref(false);
  const editing = ref<SetItemDefinition>();
  const seriesEditing = ref(false);
  const seriesMemberCount = ref(0);
  const detailKey = ref<string>();
  const activeTier = ref('');
  const editValues = reactive<Record<number, Record<string, number>>>({});
  const editSlots = ref<SetItemEquipment[][]>([]);
  const minimumSlots = computed(() =>
    Math.max(
      1,
      ...(editing.value?.tiers.map((tier) => tier.requiredCount) ?? [])
    )
  );
  const newStats = reactive<Record<number, string | undefined>>({});
  const createModal = ref<InstanceType<typeof SetItemCreateModal>>();

  const seriesCatalog = computed(() => {
    const groups = new Map<string, SetItemDefinition[]>();
    catalog.value.forEach((definition) => {
      const key = definition.builtIn
        ? `builtIn:${definition.name}`
        : `custom:${definition.id}`;
      groups.set(key, [...(groups.get(key) || []), definition]);
    });
    return Array.from(groups, ([seriesKey, members]) => {
      const first = members[0];
      const counts = first.tiers.map((tier) => tier.requiredCount).join(',');
      const bonuses = (member: SetItemDefinition) =>
        JSON.stringify(
          member.tiers.map((tier) => [
            tier.requiredCount,
            Object.entries(tier.stats).sort(([a], [b]) => a.localeCompare(b)),
          ])
        );
      return {
        ...first,
        seriesKey,
        members,
        memberCount: members.length,
        jobs: [...new Set(members.map((member) => member.jobIndex))],
        completeCounts: [
          ...new Set(members.map((member) => member.completeCount)),
        ].join(' / '),
        enabledCount: members.filter((member) => member.enabled).length,
        mixedBonuses: members.some(
          (member) => bonuses(member) !== bonuses(first)
        ),
        editable: members.every(
          (member) =>
            member.tiers.map((tier) => tier.requiredCount).join(',') === counts
        ),
      };
    });
  });
  type SetItemSeries = (typeof seriesCatalog.value)[number];
  const detailSeries = computed(() =>
    seriesCatalog.value.find((series) => series.seriesKey === detailKey.value)
  );

  const filteredSeries = computed(() => {
    const search = keyword.value.trim().toLowerCase();
    return seriesCatalog.value.filter((definition) => {
      const jobMatches =
        jobFilter.value === 99 || definition.jobs.includes(jobFilter.value);
      const textMatches =
        !search ||
        definition.name.toLowerCase().includes(search) ||
        definition.members.some((member) => String(member.id).includes(search));
      return jobMatches && textMatches;
    });
  });

  const editorTitle = computed(() => {
    if (!editing.value) return '';
    if (seriesEditing.value)
      return `${editing.value.name} · ${t('setItem.action.editSeries')}`;
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
    definition.slotsCustomized ||
    definition.tiers.some((tier) => tier.customized);

  const previewEquipment = (definition: SetItemDefinition) => {
    const result: SetItemEquipment[] = [];
    definition.slots.forEach((slot) => {
      if (slot[0]) result.push(slot[0]);
    });
    return result.slice(0, 6);
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
    detailKey.value = undefined;
    seriesEditing.value = false;
    editing.value = definition;
    editSlots.value = definition.slots.map((slot) =>
      slot.map((item) => ({ ...item }))
    );
    Object.keys(editValues).forEach((key) => delete editValues[Number(key)]);
    Object.keys(newStats).forEach((key) => delete newStats[Number(key)]);
    definition.tiers.forEach((tier) => {
      editValues[tier.requiredCount] = { ...tier.stats };
    });
    activeTier.value = String(definition.tiers[0]?.requiredCount ?? '');
    editorVisible.value = true;
  };

  const openSeriesEditor = (series: SetItemSeries) => {
    if (!series.editable) return;
    openEditor(series.members[0]);
    seriesEditing.value = true;
    seriesMemberCount.value = series.memberCount;
  };

  const fillDefaults = () => {
    editSlots.value = (editing.value?.defaultSlots ?? []).map((slot) =>
      slot.map((item) => ({ ...item }))
    );
    editing.value?.tiers.forEach((tier) => {
      editValues[tier.requiredCount] = { ...tier.defaultStats };
    });
  };

  const availableEditorStats = (requiredCount: number) =>
    Object.keys(editValues[requiredCount] || {}).length >= 24
      ? []
      : [
          ...SET_ITEM_STAT_KEYS,
          ...SET_ITEM_PERCENT_BASES.map((key) => `${key}Pct`),
        ].filter((stat) => !(stat in (editValues[requiredCount] || {})));

  const addEditorStat = (requiredCount: number) => {
    const stat = newStats[requiredCount];
    if (!stat || !availableEditorStats(requiredCount).includes(stat)) return;
    const tier = editing.value?.tiers.find(
      (entry) => entry.requiredCount === requiredCount
    );
    editValues[requiredCount][stat] = tier?.defaultStats[stat] ?? 0;
    newStats[requiredCount] = undefined;
  };

  const removeEditorStat = (requiredCount: number, stat: string) => {
    delete editValues[requiredCount][stat];
  };

  const changeEditorStat = (
    requiredCount: number,
    previous: string,
    key: string
  ) => {
    if (key === previous || key in editValues[requiredCount]) return;
    editValues[requiredCount][key] = Math.min(
      editValues[requiredCount][previous],
      setItemStatMaximum(key)
    );
    delete editValues[requiredCount][previous];
  };

  const saveDefinition = async () => {
    if (!editing.value) return;
    if (
      !seriesEditing.value &&
      editSlots.value.some((slot) => slot.length === 0)
    ) {
      Message.warning(t('setItem.validation.emptySlot'));
      return;
    }
    saving.value = true;
    try {
      const { data } = await (seriesEditing.value
        ? updateSetItemSeries(editing.value.id, editValues)
        : updateSetItem(
            editing.value.id,
            editValues,
            editSlots.value.map((slot) => slot.map((item) => item.id))
          ));
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

  .series-warning {
    margin-bottom: 16px;
  }

  .default-value {
    display: block;
    margin-top: 4px;
    color: var(--color-text-3);
    white-space: nowrap;
  }

  .stat-editor-field {
    width: 100%;
    min-width: 0;
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
    .stat-form-item {
      flex-direction: column;
      :deep(.arco-form-item-label-col) {
        flex: none;
        padding: 0 0 6px;
      }
      :deep(.arco-form-item-wrapper-col) {
        flex: none;
        width: 100%;
      }
    }
    .modal-actions {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
