<template>
  <div class="container">
    <Breadcrumb />
    <section class="catalog-surface">
      <header class="page-header">
        <div>
          <h1>怪物目录</h1>
          <span>共 {{ filteredTotal }} 个怪物</span>
        </div>
        <a-space :wrap="true" fill class="filter-bar">
          <a-input-search
            v-model="filters.keyword"
            allow-clear
            :style="{ width: 'min(300px, 50vw)', maxWidth: '100%' }"
            placeholder="按怪物名称或ID搜索"
            search-button
            @search="applySearch"
            @press-enter="applySearch"
            @clear="applySearch"
          />
          <a-select
            v-model="filters.levelRange"
            placeholder="等级范围"
            allow-clear
            :style="{ width: '140px' }"
            @change="applySearch"
          >
            <a-option value="">全部等级</a-option>
            <a-option value="1-10">1-10</a-option>
            <a-option value="11-20">11-20</a-option>
            <a-option value="21-30">21-30</a-option>
            <a-option value="31-40">31-40</a-option>
            <a-option value="41-50">41-50</a-option>
            <a-option value="51-60">51-60</a-option>
            <a-option value="61-70">61-70</a-option>
            <a-option value="71-80">71-80</a-option>
            <a-option value="81-90">81-90</a-option>
            <a-option value="91-100">91-100</a-option>
            <a-option value="101-120">101-120</a-option>
            <a-option value="121-140">121-140</a-option>
            <a-option value="141-160">141-160</a-option>
            <a-option value="161-200">161-200</a-option>
          </a-select>
          <a-tooltip content="刷新目录">
            <a-button :loading="loading" shape="circle" @click="loadData">
              <template #icon><icon-refresh /></template>
            </a-button>
          </a-tooltip>
        </a-space>
      </header>

      <main class="catalog-results">
        <a-spin :loading="loading" tip="">
          <div v-if="page.records.length" class="mob-grid">
            <article
              v-for="mob in page.records"
              :key="mob.id"
              class="mob-card"
              :class="{ selected: selectedMob?.id === mob.id }"
              @click="selectMob(mob)"
            >
              <MobIcon :mob-id="mob.id" :alt="mob.name" />
              <div class="mob-copy">
                <strong>{{ mob.name }}</strong>
                <span>{{ mob.id }}</span>
                <small>Lv.{{ mob.stats.level || '?' }}</small>
              </div>
            </article>
          </div>
          <a-empty v-else class="empty-state" />
        </a-spin>

        <footer class="pagination-row">
          <a-pagination
            v-model:current="filters.pageNo"
            v-model:page-size="filters.pageSize"
            :total="filteredTotal"
            :page-size-options="[30, 60, 90, 120]"
            show-total
            show-page-size
            @change="loadData"
            @page-size-change="changePageSize"
          />
        </footer>
      </main>
    </section>

    <!-- 怪物详情抽屉 -->
    <a-drawer
      :visible="!!selectedMob"
      :title="selectedMob?.name || ''"
      :width="480"
      :footer="false"
      @cancel="selectedMob = null"
    >
      <template v-if="selectedMob">
        <div class="mob-detail">
          <div class="mob-preview">
            <MobIcon :mob-id="selectedMob.id" :alt="selectedMob.name" />
            <div class="mob-stats">
              <div class="stat-row">
                <span>等级</span>
                <strong>{{ selectedMob.stats.level || '?' }}</strong>
              </div>
              <div class="stat-row">
                <span>HP</span>
                <strong>{{ selectedMob.stats.maxHP?.toLocaleString() || '?' }}</strong>
              </div>
              <div class="stat-row">
                <span>经验</span>
                <strong>{{ selectedMob.stats.exp?.toLocaleString() || '?' }}</strong>
              </div>
              <div class="stat-row">
                <span>攻击力</span>
                <strong>{{ selectedMob.stats.PADamage || '?' }}</strong>
              </div>
              <div class="stat-row">
                <span>防御力</span>
                <strong>{{ selectedMob.stats.PDDamage || '?' }}</strong>
              </div>
            </div>
          </div>

          <a-divider />

          <MobDropPanel :mob="selectedMob" />
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue';
  import { MobCatalogItem, MobCatalogPage, getMobCatalog } from '@/api/mobCatalog';
  import MobIcon from './MobIcon.vue';
  import MobDropPanel from './MobDropPanel.vue';

  const loading = ref(false);
  const selectedMob = ref<MobCatalogItem | null>(null);
  const filters = reactive({
    keyword: '',
    levelRange: '',
    pageNo: 1,
    pageSize: 60,
  });
  const page = reactive<MobCatalogPage>({
    records: [],
    pageNo: 1,
    pageSize: 60,
    total: 0,
  });

  // 计算筛选后的总数
  const filteredTotal = ref(0);

  const loadData = async () => {
    loading.value = true;
    try {
      // 构建查询参数
      const params: any = {
        keyword: filters.keyword.trim() || undefined,
        pageNo: filters.pageNo,
        pageSize: filters.pageSize,
      };

      // 添加等级范围筛选
      if (filters.levelRange) {
        const [min, max] = filters.levelRange.split('-').map(Number);
        params.minLevel = min;
        params.maxLevel = max;
      }

      const { data } = await getMobCatalog(params);
      Object.assign(page, data);
      filteredTotal.value = data.total;
    } finally {
      loading.value = false;
    }
  };

  const applySearch = () => {
    filters.pageNo = 1;
    loadData();
  };

  const changePageSize = () => {
    filters.pageNo = 1;
    loadData();
  };

  const selectMob = (mob: MobCatalogItem) => {
    selectedMob.value = mob;
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
    }

    span {
      color: var(--color-text-3);
      font-size: 12px;
    }
  }

  .filter-bar {
    justify-content: flex-end;
  }

  .catalog-results {
    display: flex;
    min-width: 0;
    flex-direction: column;
    padding: 16px;
  }

  .mob-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(194px, 1fr));
    gap: 10px;
    align-content: start;
  }

  .mob-card {
    display: flex;
    height: 82px;
    align-items: center;
    gap: 11px;
    overflow: hidden;
    padding: 12px;
    border: 1px solid var(--color-neutral-3);
    border-radius: 7px;
    background: var(--color-bg-2);
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      border-color: rgb(var(--primary-5));
      box-shadow: 0 4px 12px rgb(0 0 0 / 8%);
    }

    &.selected {
      border-color: rgb(var(--primary-6));
      background: var(--color-primary-light-1);
    }
  }

  .mob-copy {
    min-width: 0;

    strong {
      display: block;
      color: var(--color-text-1);
      font-size: 13px;
      line-height: 18px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
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

  .mob-detail {
    .mob-preview {
      display: flex;
      gap: 20px;
      align-items: flex-start;
    }

    .mob-stats {
      flex: 1;

      .stat-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid var(--color-neutral-2);

        span {
          color: var(--color-text-2);
        }

        strong {
          color: var(--color-text-1);
        }
      }
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
</style>
