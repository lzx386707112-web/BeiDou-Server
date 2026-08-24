<template>
  <div class="container">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('mapDetect.title')">
      <a-row :gutter="12" align="center">
        <a-col :flex="'1 1 320px'">
          <a-cascader
            v-model="mapId"
            :options="mapTree"
            :loading="treeLoading"
            :placeholder="$t('mapDetect.selectPlaceholder')"
            allow-search
            allow-clear
            :virtual-list-props="{ height: 300 }"
            @change="onMapChange"
          />
        </a-col>
        <a-col :flex="'0 0 200px'">
          <a-input
            v-model="mapId"
            :placeholder="$t('mapDetect.manualInput')"
            allow-clear
            @keydown.enter="onDetect"
          />
        </a-col>
        <a-col :flex="'0 0 auto'">
          <a-space>
            <a-button type="primary" :loading="loading" @click="onDetect">
              {{ $t('mapDetect.detect') }}
            </a-button>
            <a-button @click="onReset">{{ $t('mapDetect.reset') }}</a-button>
          </a-space>
        </a-col>
        <a-col :flex="'0 0 auto'">
          <a-space>
            <a-button
              v-for="ex in examples"
              :key="ex"
              size="mini"
              @click="mapId = ex; onDetect()"
            >
              {{ ex }}
            </a-button>
          </a-space>
        </a-col>
      </a-row>

      <a-alert
        v-if="result && !result.mapExists"
        type="error"
        :content="result.note || $t('mapDetect.mapNotExist')"
        style="margin-top: 16px"
      />

      <template v-if="result && result.mapExists">
        <!-- 地图信息 -->
        <a-card v-if="result.mapInfo" :title="$t('mapDetect.mapInfoTitle')" size="small" style="margin-top: 16px">
          <a-descriptions :column="{ xs: 1, sm: 2, md: 3 }" bordered size="small">
            <a-descriptions-item :label="$t('mapDetect.mapId')">{{ result.mapInfo.mapId }}</a-descriptions-item>
            <a-descriptions-item :label="$t('mapDetect.mapName')">{{ result.mapInfo.name || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="$t('mapDetect.region')">{{ result.mapInfo.region || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="$t('mapDetect.hasMonster')">
              <a-tag :color="result.mapInfo.hasMonster ? 'red' : 'green'">
                {{ result.mapInfo.hasMonster ? $t('mapDetect.yes') : $t('mapDetect.no') }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item :label="$t('mapDetect.monsterCount')">
              {{ result.mapInfo.monsters?.length ?? 0 }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('mapDetect.npcCount')">
              {{ result.mapInfo.npcCount ?? 0 }}
            </a-descriptions-item>
          </a-descriptions>

          <div style="margin-top: 12px">
            <a-divider orientation="left" style="margin: 8px 0">
              {{ $t('mapDetect.monsters') }} ({{ result.mapInfo.monsters?.length ?? 0 }})
            </a-divider>
            <a-space v-if="result.mapInfo.monsters?.length" wrap>
              <a-tag v-for="m in result.mapInfo.monsters" :key="m.id" color="red" style="font-size: 12px">
                {{ m.name || '未知' }} #{{ m.id }}
              </a-tag>
            </a-space>
            <span v-else style="color: var(--color-text-3)">{{ $t('mapDetect.noMonsters') }}</span>
          </div>

          <div style="margin-top: 12px">
            <a-divider orientation="left" style="margin: 8px 0">
              {{ $t('mapDetect.npcs') }} ({{ result.mapInfo.npcCount ?? 0 }})
            </a-divider>
            <a-space v-if="result.mapInfo.npcs?.length" wrap>
              <a-tag v-for="n in result.mapInfo.npcs" :key="n.id" color="arcoblue" style="font-size: 12px">
                {{ n.name || '未知' }} #{{ n.id }}
              </a-tag>
            </a-space>
            <span v-else style="color: var(--color-text-3)">{{ $t('mapDetect.noNpcs') }}</span>
          </div>
        </a-card>

        <!-- 概览 -->
        <a-divider>{{ $t('mapDetect.summary') }}</a-divider>
        <a-row :gutter="12">
          <a-col :span="6">
            <a-statistic :title="$t('mapDetect.total')" :value="result.total" />
          </a-col>
          <a-col :span="6">
            <a-statistic :title="$t('mapDetect.ok')" :value="result.ok" :value-from="0" />
          </a-col>
          <a-col :span="6">
            <a-statistic :title="$t('mapDetect.warn')" :value="result.warn" :value-style="{ color: '#ff7d00' }" />
          </a-col>
          <a-col :span="6">
            <a-statistic :title="$t('mapDetect.error')" :value="result.error" :value-style="{ color: '#f53f3f' }" />
          </a-col>
        </a-row>
        <a-row v-if="result.crashRiskCount && result.crashRiskCount > 0" style="margin-top: 8px">
          <a-col :span="24">
            <a-alert type="error" :title="'🚨 ' + $t('mapDetect.crashRisk') + ': ' + result.crashRiskCount" />
          </a-col>
        </a-row>

        <!-- 问题汇总 -->
        <a-divider>{{ $t('mapDetect.problems') }}</a-divider>
        <a-table
          v-if="problemNodes.length"
          row-key="idx"
          :data="problemNodes"
          :loading="loading"
          :pagination="false"
          :bordered="{ cell: true }"
          size="small"
        >
          <template #columns>
            <a-table-column :title="$t('mapDetect.category')" data-index="categoryLabel" :width="110" />
            <a-table-column :title="$t('mapDetect.colRef')" data-index="ref" :width="160" />
            <a-table-column :title="$t('mapDetect.colStatus')" :width="90">
              <template #cell="{ record }">
                <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column :title="$t('mapDetect.colFunc')" data-index="functionDesc" />
            <a-table-column :title="$t('mapDetect.colMsg')" data-index="message" />
          </template>
        </a-table>
        <a-empty v-else :description="$t('mapDetect.noProblem')" />

        <!-- 分类检测 -->
        <a-divider />
        <a-collapse :default-active-key="defaultActive" accordion>
          <a-collapse-item v-for="cat in result.categories" :key="cat.category" :name="cat.category">
            <template #header>
              <a-space>
                <span>{{ cat.label }}</span>
                <a-badge :count="cat.total" :max-count="99999" :number-style="{ backgroundColor: '#86909c' }" />
                <a-tag v-if="cat.error" color="red">ERROR {{ cat.error }}</a-tag>
                <a-tag v-if="cat.warn" color="orange">WARN {{ cat.warn }}</a-tag>
                <a-tag v-if="cat.ok" color="green">OK {{ cat.ok }}</a-tag>
                <a-tag v-if="cat.info" color="gray">INFO {{ cat.info }}</a-tag>
                <a-tag v-if="crashCountInCategory(cat)" color="red" style="font-weight:bold">CRASH {{ crashCountInCategory(cat) }}</a-tag>
              </a-space>
            </template>
            <a-table
              row-key="rid"
              :data="cat.nodes"
              :loading="loading"
              :pagination="cat.nodes.length > 50 ? { pageSize: 50 } : false"
              :bordered="{ cell: true }"
              size="small"
            >
              <template #columns>
                <a-table-column :title="$t('mapDetect.colRef')" data-index="ref" :width="170" />
                <a-table-column :title="$t('mapDetect.colType')" data-index="refType" :width="90" />
                <a-table-column :title="$t('mapDetect.colStatus')" :width="90">
                  <template #cell="{ record }">
                    <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
                  </template>
                </a-table-column>
                <a-table-column :title="$t('mapDetect.colFunc')" data-index="functionDesc" />
                <a-table-column :title="$t('mapDetect.colMsg')" data-index="message" />
                <a-table-column :title="$t('mapDetect.crashRisk')" :width="100">
                  <template #cell="{ record }">
                    <a-tag v-if="record.crashRisk === 'CRASH'" color="red">CRASH</a-tag>
                    <a-tag v-else-if="record.crashRisk === 'DEGRADED'" color="orange">DEGRADED</a-tag>
                    <span v-else style="color: var(--color-text-3)">-</span>
                  </template>
                </a-table-column>
                <a-table-column :title="$t('mapDetect.detail')" :width="200">
                  <template #cell="{ record }">
                    <span v-if="record.meta && Object.keys(record.meta).length" class="meta">
                      <span v-for="(v, k) in record.meta" :key="k" class="meta-item">{{ k }}={{ v }}</span>
                    </span>
                    <span v-else>-</span>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </a-collapse-item>
        </a-collapse>
      </template>
    </a-card>

    <!-- 地图对比区 -->
    <a-card :title="$t('mapDetect.compare')" size="small" style="margin-top: 16px">
      <a-row :gutter="12" align="center">
        <a-col :flex="'1 1 320px'">
          <a-input
            v-model="mapId2"
            :placeholder="$t('mapDetect.compareInput')"
            allow-clear
          />
        </a-col>
        <a-col :flex="'0 0 auto'">
          <a-button type="primary" :loading="compareLoading" @click="onCompare">
            {{ $t('mapDetect.compareBtn') }}
          </a-button>
        </a-col>
      </a-row>

      <template v-if="compareResult">
        <a-alert
          :type="compareResult.diffs?.some((d: any) => d.crashRisk === 'CRASH') ? 'error' : 'success'"
          :content="compareResult.crashSummary || ''"
          style="margin-top: 12px"
        />
        <a-table
          v-if="compareResult.diffs?.length"
          :data="compareResult.diffs"
          :pagination="false"
          :bordered="{ cell: true }"
          size="small"
          style="margin-top: 12px"
        >
          <template #columns>
            <a-table-column :title="$t('mapDetect.category')" data-index="category" :width="80" />
            <a-table-column :title="$t('mapDetect.colRef')" data-index="description" :width="120" />
            <a-table-column :title="compareResult.mapIdA" data-index="valueA" />
            <a-table-column :title="compareResult.mapIdB" data-index="valueB" />
            <a-table-column :title="$t('mapDetect.crashRisk')" :width="100">
              <template #cell="{ record }">
                <a-tag v-if="record.crashRisk === 'CRASH'" color="red">CRASH</a-tag>
                <a-tag v-else-if="record.crashRisk === 'DEGRADED'" color="orange">DEGRADED</a-tag>
                <span v-else style="color: var(--color-text-3)">-</span>
              </template>
            </a-table-column>
          </template>
        </a-table>
        <a-empty v-else :description="$t('mapDetect.noDiff')" style="margin-top: 12px" />
      </template>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed, onMounted } from 'vue';
  import {
    detectMap,
    getMapTree,
    compareMap,
    MapDetectResult,
    MapDetectNode,
    MapTreeItem,
    MapCompareResult,
  } from '@/api/mapDetect';

  const mapId = ref('271000000');
  const loading = ref(false);
  const result = ref<MapDetectResult | null>(null);
  const examples = ['271000000', '100000000', '200000000', '000000000'];

  const mapTree = ref<MapTreeItem[]>([]);
  const treeLoading = ref(false);

  const loadTree = async () => {
    treeLoading.value = true;
    try {
      const { data } = await getMapTree();
      mapTree.value = data || [];
    } catch (e) {
      // 拦截器已弹错误提示，手动输入 ID 仍可用
    } finally {
      treeLoading.value = false;
    }
  };

  onMounted(() => {
    loadTree();
  });

  const onMapChange = (
    value: string | number | Record<string, any> | undefined
  ) => {
    // 级联选中具体地图（叶子 value = 9 位补零 id）后自动检测
    if (value !== undefined && value !== null && value !== '') onDetect();
  };

  const defaultActive = computed(() => result.value?.categories.map((c) => c.category) ?? []);

  const problemNodes = computed(() => {
    if (!result.value) return [];
    const order: Record<string, number> = { ERROR: 0, WARN: 1, INFO: 2, OK: 3 };
    const labelMap = new Map(result.value.categories.map((c) => [c.category, c.label]));
    const list: any[] = [];
    result.value.categories.forEach((cat) => {
      cat.nodes.forEach((n: MapDetectNode) => {
        if (n.status === 'ERROR' || n.status === 'WARN') {
          list.push({ ...n, categoryLabel: labelMap.get(n.category) ?? n.category, idx: `${cat.category}-${n.ref}` });
        }
      });
    });
    return list.sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));
  });

  const statusColor = (s: string) => {
    return { OK: 'green', WARN: 'orange', ERROR: 'red', INFO: 'gray' }[s] ?? 'gray';
  };
  const statusText = (s: string) => {
    return { OK: '正常', WARN: '警告', ERROR: '错误', INFO: '提示' }[s] ?? s;
  };

  const crashCountInCategory = (cat: any) => {
    return cat.nodes?.filter((n: any) => n.crashRisk === 'CRASH').length ?? 0;
  };

  const onDetect = async () => {
    if (!mapId.value || !mapId.value.trim()) return;
    loading.value = true;
    try {
      const { data } = await detectMap({ mapId: mapId.value.trim() });
      result.value = data;
    } catch (e) {
      // 拦截器已弹错误提示
    } finally {
      loading.value = false;
    }
  };

  const onReset = () => {
    mapId.value = '';
    result.value = null;
  };

  // 地图对比
  const mapId2 = ref('');
  const compareResult = ref<MapCompareResult | null>(null);
  const compareLoading = ref(false);

  const onCompare = async () => {
    if (!mapId.value?.trim() || !mapId2.value?.trim()) return;
    compareLoading.value = true;
    compareResult.value = null;
    try {
      const { data } = await compareMap({ mapId: mapId.value.trim(), mapId2: mapId2.value.trim() });
      compareResult.value = data;
    } catch (e) {
      // 拦截器已弹错误提示
    } finally {
      compareLoading.value = false;
    }
  };
</script>

<style scoped>
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .meta-item {
    background: var(--color-fill-2);
    border-radius: 4px;
    padding: 0 6px;
    font-size: 12px;
    color: var(--color-text-3);
  }
</style>
