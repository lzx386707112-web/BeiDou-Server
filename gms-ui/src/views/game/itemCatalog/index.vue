<template>
  <div class="container">
    <Breadcrumb />
    <section class="catalog-surface">
      <header class="page-header">
        <div>
          <h1>物品目录</h1>
          <span>共 {{ page.total }} 件物品</span>
        </div>
        <a-space :wrap="true" fill class="filter-bar">
          <a-input-search
            v-model="filters.keyword"
            allow-clear
            :style="{ width: 'min(360px, 50vw)', maxWidth: '100%' }"
            placeholder="按物品名称或物品ID搜索"
            search-button
            @search="applySearch"
            @press-enter="applySearch"
            @clear="applySearch"
          />
          <a-tooltip content="刷新目录">
            <a-button :loading="loading" shape="circle" @click="loadData">
              <template #icon><icon-refresh /></template>
            </a-button>
          </a-tooltip>
        </a-space>
      </header>

      <div class="catalog-layout">
        <aside class="category-list">
          <button
            type="button"
            :class="{ active: filters.category === '' }"
            @click="selectAll"
          >
            <span>全部物品</span>
            <strong>{{ totalCount }}</strong>
          </button>
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
        </aside>

        <main class="catalog-results">
          <a-spin :loading="loading" tip="">
            <div v-if="page.records.length" class="item-grid">
              <a-popover
                v-for="item in page.records"
                :key="item.id"
                position="right"
                trigger="hover"
                :content-style="{ padding: 0, background: 'transparent' }"
              >
                <article class="item-card">
                  <ItemIcon :item-id="item.id" :alt="item.name" />
                  <div class="item-copy">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.id }}</span>
                    <small>{{ categoryName(item.category) }}</small>
                  </div>
                </article>
                <template #content>
                  <ItemTooltip :item="item" />
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
  import {
    ItemCatalogItem,
    ItemCatalogPage,
    getItemCatalog,
  } from '@/api/itemCatalog';
  import ItemIcon from './ItemIcon.vue';
  import ItemTooltip from './ItemTooltip.vue';

  const loading = ref(false);
  const filters = reactive({
    keyword: '',
    category: '',
    pageNo: 1,
    pageSize: 60,
  });
  const page = reactive<ItemCatalogPage>({
    records: [],
    categories: [],
    pageNo: 1,
    pageSize: 60,
    total: 0,
  });

  const totalCount = computed(() =>
    page.categories.reduce((total, category) => total + category.count, 0)
  );

  const categoryName = (category: string) => {
    const names: Record<string, string> = {
      Consume: '消耗物品',
      Etc: '其他物品',
      Install: '设置物品',
      Cash: '现金物品',
      Pet: '宠物',
      Special: '特殊物品',
    };
    return names[category] || category;
  };

  const loadData = async () => {
    loading.value = true;
    try {
      const { data } = await getItemCatalog({
        keyword: filters.keyword.trim() || undefined,
        category: filters.category || undefined,
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
    filters.pageNo = 1;
    loadData();
  };

  const selectAll = () => {
    filters.category = '';
    filters.pageNo = 1;
    loadData();
  };

  const changePageSize = () => {
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

  .item-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(194px, 1fr));
    gap: 10px;
    align-content: start;
  }

  .item-card {
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

  .item-copy {
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

      button {
        width: auto;
        min-width: 118px;
        flex: 0 0 auto;
      }
    }

    .item-grid {
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    }
  }

  @media (max-width: 520px) {
    .catalog-results {
      padding: 10px;
    }

    .item-grid {
      grid-template-columns: 1fr;
    }

    .pagination-row {
      overflow-x: auto;
      justify-content: flex-start;
    }
  }
</style>
