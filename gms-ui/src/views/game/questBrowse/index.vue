<template>
  <div class="container">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('questBrowse.title')">
      <a-row :gutter="12" align="center">
        <a-col :flex="'1 1 360px'">
          <a-cascader
            v-model="selectedPath"
            :options="tree"
            :loading="treeLoading"
            :placeholder="$t('questBrowse.selectPlaceholder')"
            allow-search
            allow-clear
            change-on-select
            :virtual-list-props="{ height: 300 }"
            @change="onPathChange"
          />
        </a-col>
        <a-col :flex="'0 0 auto'">
          <a-space>
            <a-button type="primary" @click="loadAll">{{ $t('questBrowse.all') }}</a-button>
          </a-space>
        </a-col>
      </a-row>

      <div v-if="listLoaded" style="margin-top: 16px">
        <a-space style="margin-bottom: 8px">
          <a-tag color="arcoblue">{{ $t('questBrowse.total', { count: quests.length }) }}</a-tag>
        </a-space>
        <a-table
          :data="quests"
          :pagination="{ pageSize: 50, showPageSize: true, pageSizeOptions: [20,50,100] }"
          :scroll="{ x: 800, y: 600 }"
          :bordered="false"
          size="small"
          @row-click="onRowClick"
        >
          <template #columns>
            <a-table-column :title="$t('questBrowse.colId')" data-index="questId" :width="80" :sortable="{sorter:(a: any,b: any) => Number(a.questId)-Number(b.questId), sortDirections: ['ascend','descend'] as const}" />
            <a-table-column :title="$t('questBrowse.colName')" data-index="name" :width="200" :ellipsis="true" />
            <a-table-column :title="$t('questBrowse.colLevel')" :width="120" :sortable="{sorter:(a: any,b: any) => (a.levelMin??0)-(b.levelMin??0), sortDirections: ['ascend','descend'] as const}">
              <template #cell="{ record }">
                <span v-if="record.levelMin != null || record.levelMax != null">
                  {{ record.levelMin ?? '?' }} – {{ record.levelMax ?? '?' }}
                </span>
                <span v-else style="color: var(--color-text-3)">{{ $t('questBrowse.unlimited') }}</span>
              </template>
            </a-table-column>
            <a-table-column :title="$t('questBrowse.colStartNpc')" :width="140">
              <template #cell="{ record }">
                <a-space v-if="record.startNpcId" align="center" :size="4">
                  <img :src="npcIconUrl(record.startNpcId)" alt="" style="height: 24px; image-rendering: pixelated" @error="onNpcImgError" />
                  <span>{{ record.startNpcName || record.startNpcId }}</span>
                </a-space>
                <span v-else style="color: var(--color-text-3)">-</span>
              </template>
            </a-table-column>
            <a-table-column :title="$t('questBrowse.colEndNpc')" :width="140">
              <template #cell="{ record }">
                <a-space v-if="record.endNpcId" align="center" :size="4">
                  <img :src="npcIconUrl(record.endNpcId)" alt="" style="height: 24px; image-rendering: pixelated" @error="onNpcImgError" />
                  <span>{{ record.endNpcName || record.endNpcId }}</span>
                </a-space>
                <span v-else style="color: var(--color-text-3)">-</span>
              </template>
            </a-table-column>
            <a-table-column :title="$t('questBrowse.colChain')" :width="60" align="center">
              <template #cell="{ record }">
                <a-tag v-if="record.inChain" color="orangered" size="small">{{ $t('questBrowse.yes') }}</a-tag>
                <span v-else style="color: var(--color-text-3)">-</span>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </div>

      <a-empty v-else-if="!treeLoading && listLoaded === false" :description="$t('questBrowse.noQuests')" style="margin-top: 40px" />
    </a-card>

    <!-- 任务详情抽屉 -->
    <a-drawer
      :visible="drawerVisible"
      :title="$t('questBrowse.detail')"
      :width="560"
      :footer="false"
      @cancel="drawerVisible = false"
    >
      <template v-if="detail">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item :label="$t('questBrowse.questId')">{{ detail.questId }}</a-descriptions-item>
          <a-descriptions-item :label="$t('questBrowse.questName')">{{ detail.name }}</a-descriptions-item>
          <a-descriptions-item :label="$t('questBrowse.level')">
            <span v-if="detail.levelMin != null || detail.levelMax != null">
              {{ detail.levelMin ?? '?' }} – {{ detail.levelMax ?? '?' }}
            </span>
            <span v-else>{{ $t('questBrowse.unlimited') }}</span>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('questBrowse.startNpc')">
            <a-space align="center">
              <img v-if="detail.startNpcId" :src="npcIconUrl(detail.startNpcId)" alt="" style="height: 48px; image-rendering: pixelated" @error="onNpcImgError" />
              <span>{{ detail.startNpcName || '-' }}</span>
              <span v-if="detail.startNpcId" style="color: var(--color-text-3)">({{ detail.startNpcId }})</span>
            </a-space>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('questBrowse.endNpc')">
            <a-space align="center">
              <img v-if="detail.endNpcId" :src="npcIconUrl(detail.endNpcId)" alt="" style="height: 48px; image-rendering: pixelated" @error="onNpcImgError" />
              <span>{{ detail.endNpcName || '-' }}</span>
              <span v-if="detail.endNpcId" style="color: var(--color-text-3)">({{ detail.endNpcId }})</span>
            </a-space>
          </a-descriptions-item>
          <a-descriptions-item v-if="detail.parentName" :label="$t('questBrowse.parentName')">
            {{ detail.parentName }}
            <span v-if="detail.order != null"> ({{ $t('questBrowse.order') }}: {{ detail.order }})</span>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider />
        <a-typography-title :heading="6" style="margin-bottom: 8px">{{ $t('questBrowse.contentStart') }}</a-typography-title>
        <a-typography-paragraph v-if="detail.contentStart" style="white-space: pre-wrap; margin-bottom: 16px">{{ detail.contentStart }}</a-typography-paragraph>
        <a-typography-paragraph v-else style="color: var(--color-text-3); margin-bottom: 16px">-</a-typography-paragraph>

        <a-typography-title :heading="6" style="margin-bottom: 8px">{{ $t('questBrowse.contentProgress') }}</a-typography-title>
        <a-typography-paragraph v-if="detail.contentProgress" style="white-space: pre-wrap; margin-bottom: 16px">{{ detail.contentProgress }}</a-typography-paragraph>
        <a-typography-paragraph v-else style="color: var(--color-text-3); margin-bottom: 16px">-</a-typography-paragraph>

        <a-typography-title :heading="6" style="margin-bottom: 8px">{{ $t('questBrowse.contentComplete') }}</a-typography-title>
        <a-typography-paragraph v-if="detail.contentComplete" style="white-space: pre-wrap; margin-bottom: 16px">{{ detail.contentComplete }}</a-typography-paragraph>
        <a-typography-paragraph v-else style="color: var(--color-text-3); margin-bottom: 16px">-</a-typography-paragraph>

        <template v-if="detail.chain.length > 1">
          <a-divider />
          <a-typography-title :heading="6" style="margin-bottom: 8px">{{ $t('questBrowse.chainTitle') }}</a-typography-title>
          <a-steps :current="chainCurrent" small style="margin-bottom: 12px">
            <a-step v-for="item in detail.chain" :key="item.questId" :status="item.current ? 'process' : 'finish'">
              <template #title>
                <a-link @click="openQuest(item.questId)">{{ item.name || item.questId }}</a-link>
              </template>
              <template #description>
                <span v-if="item.levelMin != null">Lv.{{ item.levelMin }}+</span>
              </template>
            </a-step>
          </a-steps>
        </template>
      </template>
      <a-spin v-else style="display: flex; justify-content: center; padding: 40px" />
    </a-drawer>
  </div>
</template>

<script lang="ts" setup>
  import { ref, onMounted, computed } from 'vue';
  import {
    getQuestTownTree,
    getQuestList,
    getQuestDetail,
    QuestTreeItem,
    QuestSummary,
    QuestDetail,
  } from '@/api/questBrowse';
  import { getIconUrl } from '@/utils/mapleStoryAPI';

  const tree = ref<QuestTreeItem[]>([]);
  const treeLoading = ref(false);
  const selectedPath = ref<string[] | undefined>(undefined);

  const quests = ref<QuestSummary[]>([]);
  const listLoaded = ref<boolean | null>(null);

  const drawerVisible = ref(false);
  const detail = ref<QuestDetail | null>(null);

  const chainCurrent = computed(() => {
    if (!detail.value) return 1;
    const idx = detail.value.chain.findIndex((c) => c.current);
    return idx >= 0 ? idx + 1 : 1;
  });

  onMounted(async () => {
    treeLoading.value = true;
    try {
      const { data } = await getQuestTownTree();
      tree.value = data || [];
    } catch {
      // 拦截器已弹错误提示
    } finally {
      treeLoading.value = false;
    }
  });

  const onPathChange = (value: any) => {
    if (!value || !Array.isArray(value) || value.length === 0) {
      quests.value = [];
      listLoaded.value = null;
      return;
    }
    const region = value[0] as string;
    const town = value.length > 1 ? (value[1] as string) : undefined;
    loadQuests(region, town);
  };

  const loadAll = () => {
    selectedPath.value = undefined;
    loadQuests(undefined, undefined);
  };

  const loadQuests = async (region?: string, town?: string) => {
    try {
      const { data } = await getQuestList({ region, town });
      quests.value = data || [];
      listLoaded.value = quests.value.length > 0;
    } catch {
      quests.value = [];
      listLoaded.value = false;
    }
  };

  const onRowClick = async (record: any) => {
    drawerVisible.value = true;
    detail.value = null;
    try {
      const { data } = await getQuestDetail({ questId: record.questId });
      detail.value = data;
    } catch {
      detail.value = null;
    }
  };

  const openQuest = async (questId: string) => {
    detail.value = null;
    try {
      const { data } = await getQuestDetail({ questId });
      detail.value = data;
    } catch {
      detail.value = null;
    }
  };

  const npcIconUrl = (npcId?: string) => {
    if (!npcId) return '';
    return getIconUrl('npc', Number(npcId));
  };

  const onNpcImgError = (e: Event) => {
    (e.target as HTMLImageElement).style.display = 'none';
  };
</script>
