<template>
  <div class="container">
    <Breadcrumb />
    <section class="catalog-surface">
      <header class="page-header">
        <div>
          <h1>{{ $t('equipmentCatalog.title') }}</h1>
          <span>{{ $t('equipmentCatalog.total', { count: page.total }) }}</span>
        </div>
        <a-space :wrap="true" fill class="filter-bar">
          <a-input-search
            v-model="filters.keyword"
            allow-clear
            :style="{ width: 'min(360px, 50vw)', maxWidth: '100%' }"
            :placeholder="$t('equipmentCatalog.search')"
            search-button
            @search="applySearch"
            @press-enter="applySearch"
            @clear="applySearch"
          />
          <a-select
            v-model="filters.job"
            :placeholder="$t('equipmentCatalog.job.placeholder')"
            allow-clear
            :style="{ width: '140px' }"
            @change="onJobChange"
          >
            <a-option :value="0">{{ $t('equipmentCatalog.job.all') }}</a-option>
            <a-option :value="1">{{ $t('equipmentCatalog.job.warrior') }}</a-option>
            <a-option :value="2">{{ $t('equipmentCatalog.job.magician') }}</a-option>
            <a-option :value="4">{{ $t('equipmentCatalog.job.bowman') }}</a-option>
            <a-option :value="8">{{ $t('equipmentCatalog.job.thief') }}</a-option>
            <a-option :value="16">{{ $t('equipmentCatalog.job.pirate') }}</a-option>
          </a-select>
          <a-input-group compact>
            <a-input-number
              v-model="filters.minLevel"
              :placeholder="$t('equipmentCatalog.level.min')"
              :min="0"
              :max="filters.maxLevel || 255"
              :style="{ width: '100px' }"
              @change="onLevelChange"
            />
            <a-input-number
              v-model="filters.maxLevel"
              :placeholder="$t('equipmentCatalog.level.max')"
              :min="filters.minLevel || 0"
              :max="255"
              :style="{ width: '100px' }"
              @change="onLevelChange"
            />
          </a-input-group>
          <a-radio-group v-model="filters.cash" type="button" @change="onCashChange">
            <a-radio value="">{{ $t('equipmentCatalog.cash.all') }}</a-radio>
            <a-radio value="cash">现金 ({{ page.cashCount }})</a-radio>
            <a-radio value="normal">普通 ({{ page.nonCashCount }})</a-radio>
          </a-radio-group>
          <a-tooltip :content="$t('equipmentCatalog.refresh')">
            <a-button :loading="loading" shape="circle" @click="loadData">
              <template #icon><icon-refresh /></template>
            </a-button>
          </a-tooltip>
        </a-space>
      </header>

      <div class="catalog-layout">
        <aside class="category-list">
          <div class="group-tabs">
            <button
              type="button"
              :class="{ active: groupMode === 'category' }"
              @click="switchGroup('category')"
            >
              {{ $t('equipmentCatalog.group.category') }}
            </button>
            <button
              type="button"
              :class="{ active: groupMode === 'equipKind' }"
              @click="switchGroup('equipKind')"
            >
              {{ $t('equipmentCatalog.group.equipKind') }}
            </button>
          </div>
          <button
            type="button"
            :class="{ active: currentFilter === '' }"
            @click="selectAll"
          >
            <span>{{ groupMode === 'category' ? $t('equipmentCatalog.category.all') : $t('equipmentCatalog.equipKind.all') }}</span>
            <strong>{{ groupMode === 'category' ? allCategoryCount : allEquipKindCount }}</strong>
          </button>
          <template v-if="groupMode === 'category'">
            <button
              v-for="category in page.categories"
              :key="category.key"
              type="button"
              :class="{ active: filters.category === category.key }"
              @click="selectCategory(category.key)"
            >
              <span>{{ categoryName(category.key) }}</span>
              <strong>{{ category.count }}</strong>
            </button>
          </template>
          <template v-else>
            <button
              v-for="wt in page.weaponTypes"
              :key="wt.key"
              type="button"
              :class="{ active: filters.weaponType === wt.key }"
              @click="selectEquipKind(wt.key)"
            >
              <span>{{ wt.key }}</span>
              <strong>{{ wt.count }}</strong>
            </button>
          </template>
        </aside>

        <main class="catalog-results">
          <a-spin :loading="loading" tip="">
            <div v-if="page.records.length" class="equipment-grid">
              <a-popover
                v-for="item in page.records"
                :key="item.id"
                position="right"
                trigger="hover"
                :content-style="{ padding: 0, background: 'transparent' }"
              >
                <article class="equipment-card">
                  <EquipmentIcon :item-id="item.id" :alt="item.name" />
                  <div class="equipment-copy">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.id }}</span>
                    <small>
                      {{
                        $t('equipmentCatalog.level', { level: levelOf(item) })
                      }}
                    </small>
                  </div>
                </article>
                <template #content>
                  <EquipmentTooltip :item="item" />
                </template>
              </a-popover>
            </div>
            <a-empty v-else class="empty-state" />
          </a-spin>

          <footer class="pagination-row">
            <a-pagination
              v-model:current="filters.pageNo"
              v-model:page-size="filters.pageSize"
              :total="page.total"
              :page-size-options="[30, 60, 90, 120]"
              show-total
              show-page-size
              @change="loadData"
              @page-size-change="changePageSize"
            />
          </footer>
        </main>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    EquipmentCatalogItem,
    EquipmentCatalogPage,
    getEquipmentCatalog,
  } from '@/api/equipmentCatalog';
  import EquipmentIcon from './EquipmentIcon.vue';
  import EquipmentTooltip from './EquipmentTooltip.vue';

  const { t } = useI18n();
  const loading = ref(false);
  const filters = reactive({
    keyword: '',
    category: '',
    cash: '' as '' | 'cash' | 'normal',
    weaponType: '',
    job: 0,
    minLevel: null as number | null,
    maxLevel: null as number | null,
    pageNo: 1,
    pageSize: 60,
  });
  const page = reactive<EquipmentCatalogPage>({
    records: [],
    categories: [],
    weaponTypes: [],
    cashCount: 0,
    nonCashCount: 0,
    pageNo: 1,
    pageSize: 60,
    total: 0,
  });
  const groupMode = ref<'category' | 'equipKind'>('category');
  const allCategoryCount = computed(() =>
    page.categories.reduce((total, category) => total + category.count, 0)
  );
  const allEquipKindCount = computed(() =>
    (page.weaponTypes || []).reduce((total, kind) => total + kind.count, 0)
  );
  const currentFilter = computed(() =>
    groupMode.value === 'category' ? filters.category : filters.weaponType
  );
  const categoryName = (category: string) =>
    t(`equipmentCatalog.category.${category}`);
  const levelOf = (item: EquipmentCatalogItem) => item.stats.reqLevel || 0;

  const loadData = async () => {
    loading.value = true;
    try {
      const { data } = await getEquipmentCatalog({
        keyword: filters.keyword.trim() || undefined,
        category: filters.category || undefined,
        cash: filters.cash === '' ? undefined : filters.cash === 'cash',
        weaponType: filters.weaponType || undefined,
        job: filters.job || undefined,
        minLevel: filters.minLevel || undefined,
        maxLevel: filters.maxLevel || undefined,
        pageNo: filters.pageNo,
        pageSize: filters.pageSize,
      });
      Object.assign(page, data);
    } finally {
      loading.value = false;
    }
  };

  const applySearch = () => {
    filters.pageNo = 1;
    loadData();
  };

  const selectCategory = (category: string) => {
    filters.category = category;
    filters.weaponType = '';
    filters.pageNo = 1;
    loadData();
  };

  const selectEquipKind = (kind: string) => {
    filters.weaponType = kind;
    filters.category = '';
    filters.pageNo = 1;
    loadData();
  };

  const selectAll = () => {
    if (groupMode.value === 'category') {
      filters.category = '';
    } else {
      filters.weaponType = '';
    }
    filters.pageNo = 1;
    loadData();
  };

  const switchGroup = (mode: 'category' | 'equipKind') => {
    groupMode.value = mode;
    filters.category = '';
    filters.weaponType = '';
    filters.pageNo = 1;
    loadData();
  };

  const changePageSize = () => {
    filters.pageNo = 1;
    loadData();
  };

  const onCashChange = () => {
    filters.pageNo = 1;
    loadData();
  };

  const onJobChange = () => {
    filters.pageNo = 1;
    loadData();
  };

  const onLevelChange = () => {
    filters.pageNo = 1;
    loadData();
  };

  onMounted(loadData);
</script>

<style scoped lang="less">
  .catalog-surface {
    min-height: calc(100vh - 132px);
    overflow: hidden;
    border: 1px solid var(--color-neutral-3);
    border-radius: 8px;
    background: var(--color-bg-2);
  }

  .page-header {
    display: flex;
    min-height: 76px;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 14px 20px;
    border-bottom: 1px solid var(--color-neutral-3);

    h1 {
      margin: 0;
      color: var(--color-text-1);
      font-size: 20px;
      line-height: 28px;
      letter-spacing: 0;
    }

    span {
      color: var(--color-text-3);
      font-size: 12px;
    }
  }

  .filter-bar {
    justify-content: flex-end;

    :deep(.arco-space-item) {
      flex-shrink: 0;
    }
  }

  .catalog-layout {
    display: grid;
    grid-template-columns: 190px minmax(0, 1fr);
    min-height: calc(100vh - 209px);
  }

  .category-list {
    padding: 10px;
    border-right: 1px solid var(--color-neutral-3);
    background: var(--color-fill-1);

    .group-tabs {
      display: flex;
      gap: 6px;
      margin-bottom: 8px;

      button {
        flex: 1 1 0;
        width: auto;
        min-height: 30px;
        justify-content: center;
        padding: 4px 6px;
        color: var(--color-text-2);
        border: 1px solid var(--color-border-tertiary);
        border-radius: 5px;
        background: transparent;
        cursor: pointer;
        font-size: 12px;
        font-family: inherit;

        &.active {
          color: rgb(var(--primary-6));
          border-color: rgb(var(--primary-6));
          background: var(--color-primary-light-1);
        }
      }
    }

    button {
      display: flex;
      width: 100%;
      min-height: 36px;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 7px 10px;
      color: var(--color-text-2);
      border: 0;
      border-radius: 5px;
      background: transparent;
      cursor: pointer;
      font: inherit;
      letter-spacing: 0;
      text-align: left;

      &:hover {
        background: var(--color-fill-3);
      }

      &.active {
        color: rgb(var(--primary-6));
        background: var(--color-primary-light-1);
      }

      strong {
        min-width: 30px;
        color: var(--color-text-3);
        font-size: 11px;
        text-align: right;
      }
    }
  }

  .catalog-results {
    display: flex;
    min-width: 0;
    flex-direction: column;
    padding: 16px;

    :deep(.arco-spin) {
      width: 100%;
    }
  }

  .equipment-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(194px, 1fr));
    gap: 10px;
    align-content: start;
  }

  .equipment-card {
    display: flex;
    height: 82px;
    align-items: center;
    gap: 11px;
    overflow: hidden;
    padding: 12px;
    border: 1px solid var(--color-neutral-3);
    border-radius: 7px;
    background: var(--color-bg-2);
    cursor: default;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;

    &:hover {
      border-color: rgb(var(--primary-5));
      box-shadow: 0 4px 12px rgb(0 0 0 / 8%);
    }
  }

  .equipment-copy {
    min-width: 0;

    strong {
      display: -webkit-box;
      overflow: hidden;
      color: var(--color-text-1);
      font-size: 13px;
      line-height: 18px;
      overflow-wrap: anywhere;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }

    span,
    small {
      display: block;
      margin-top: 2px;
      color: var(--color-text-3);
      font-size: 11px;
      line-height: 14px;
    }
  }

  .empty-state {
    padding: 96px 0;
  }

  .pagination-row {
    display: flex;
    justify-content: flex-end;
    margin-top: auto;
    padding-top: 18px;
  }

  @media (max-width: 900px) {
    .page-header {
      align-items: stretch;
      flex-direction: column;
    }

    .filter-bar {
      justify-content: flex-start;
      align-items: flex-start;
    }

    .catalog-layout {
      display: block;
    }

    .category-list {
      display: flex;
      overflow-x: auto;
      border-right: 0;
      border-bottom: 1px solid var(--color-neutral-3);

      .group-tabs {
        flex: 0 0 100%;
        width: 100%;
        margin-bottom: 8px;
      }

      button {
        width: auto;
        min-width: 118px;
        flex: 0 0 auto;
      }
    }

    .equipment-grid {
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    }
  }

  @media (max-width: 520px) {
    .catalog-results {
      padding: 10px;
    }

    .equipment-grid {
      grid-template-columns: 1fr;
    }

    .pagination-row {
      overflow-x: auto;
      justify-content: flex-start;
    }
  }
</style>
