<template>
  <div class="container">
    <Breadcrumb />
    <section class="catalog-surface">
      <header class="page-header">
        <div>
          <h1>职业技能预览</h1>
          <span>共 {{ page.total }} 个技能</span>
        </div>
        <a-space :wrap="true" fill class="filter-bar">
          <a-input-search
            v-model="filters.keyword"
            allow-clear
            :style="{ width: 'min(300px, 50vw)', maxWidth: '100%' }"
            placeholder="按技能名称或ID搜索"
            search-button
            @search="applySearch"
            @press-enter="applySearch"
            @clear="applySearch"
          />
          <a-select
            v-model="filters.advancement"
            :style="{ width: '120px' }"
            placeholder="转职阶段"
            allow-clear
            @change="applySearch"
          >
            <a-option :value="undefined">全部阶段</a-option>
            <a-option :value="0">初心者</a-option>
            <a-option :value="1">1转</a-option>
            <a-option :value="2">2转</a-option>
            <a-option :value="3">3转</a-option>
            <a-option :value="4">4转</a-option>
          </a-select>
          <a-tooltip content="重新加载技能目录">
            <a-button :loading="reloading" @click="reloadCatalog">
              重新加载
            </a-button>
          </a-tooltip>
          <a-tooltip content="刷新目录">
            <a-button :loading="loading" shape="circle" @click="loadData">
              <template #icon><icon-refresh /></template>
            </a-button>
          </a-tooltip>
        </a-space>
      </header>

      <div class="catalog-layout">
        <aside class="job-list">
          <button
            type="button"
            :class="{ active: filters.jobId === undefined }"
            @click="selectJob(undefined)"
          >
            <span>全部职业</span>
            <strong>{{ totalCount }}</strong>
          </button>
          <div v-for="(group, groupName) in jobGroups" :key="groupName" class="job-group">
            <div class="group-label">{{ groupName }}</div>
            <button
              v-for="job in group"
              :key="job.jobId"
              type="button"
              :class="{ active: filters.jobId === job.jobId }"
              @click="selectJob(job.jobId)"
            >
              <span>{{ job.jobName }}</span>
              <strong>{{ job.count }}</strong>
            </button>
          </div>
        </aside>

        <main class="catalog-results">
          <a-spin :loading="loading" tip="">
            <div v-if="page.records.length" class="skill-grid">
              <a-popover
                v-for="skill in page.records"
                :key="skill.id"
                position="right"
                trigger="hover"
                :content-style="{ padding: 0, background: 'transparent', maxWidth: '520px' }"
              >
                <article class="skill-card">
                  <SkillIcon :skill-id="skill.id" />
                  <div class="skill-copy">
                    <strong>{{ skill.name || `技能 ${skill.id}` }}</strong>
                    <span class="skill-id">{{ skill.id }}</span>
                    <small>{{ skill.jobName }}</small>
                  </div>
                  <div class="skill-level">
                    <a-tag size="small" color="arcoblue">Lv.{{ skill.maxLevel }}</a-tag>
                  </div>
                </article>
                <template #content>
                  <SkillDetail :skill="skill" />
                </template>
              </a-popover>
            </div>
            <a-empty
              v-else
              class="empty-state"
              :description="page.message || '没有符合条件的技能'"
            />
          </a-spin>

          <footer class="pagination-row">
            <a-pagination
              v-model:current="filters.pageNo"
              v-model:page-size="filters.pageSize"
              :total="page.total"
              :page-size-options="[60, 120, 240, 480]"
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
    SkillCatalogPage,
    SkillJobCategory,
    getSkillCatalog,
    reloadSkillCatalog,
  } from '@/api/skillCatalog';
  import SkillIcon from './SkillIcon.vue';
  import SkillDetail from './SkillDetail.vue';

  const loading = ref(false);
  const reloading = ref(false);
  const filters = reactive({
    keyword: '',
    jobId: undefined as number | undefined,
    advancement: undefined as number | undefined,
    pageNo: 1,
    pageSize: 120,
  });
  const page = reactive<SkillCatalogPage>({
    records: [],
    jobs: [],
    pageNo: 1,
    pageSize: 120,
    total: 0,
    loaded: false,
    message: '',
  });

  // 职业分组
  const jobGroups = computed(() => {
    const groups: Record<string, SkillJobCategory[]> = {
      '冒险家': [],
      '皇家骑士团': [],
      '战神': [],
      '龙神': [],
      '双弩精灵': [],
      '幻影': [],
      '隐月': [],
      '管理员': [],
    };

    page.jobs.forEach((job) => {
      const jobId = job.jobId;
      if (jobId >= 800 && jobId < 1000) {
        groups['管理员'].push(job);
      } else if (jobId < 1000) {
        groups['冒险家'].push(job);
      } else if (jobId >= 1000 && jobId < 2000) {
        groups['皇家骑士团'].push(job);
      } else if (jobId >= 2000 && jobId < 2200) {
        groups['战神'].push(job);
      } else if (jobId >= 2200 && jobId < 3000) {
        groups['龙神'].push(job);
      } else if (jobId >= 3000 && jobId < 4000) {
        groups['双弩精灵'].push(job);
      } else if (jobId >= 4000 && jobId < 5000) {
        groups['幻影'].push(job);
      } else if (jobId >= 5000) {
        groups['隐月'].push(job);
      }
    });

    // 移除空分组
    Object.keys(groups).forEach((key) => {
      if (groups[key].length === 0) {
        delete groups[key];
      }
    });

    return groups;
  });

  const totalCount = computed(() =>
    page.jobs.reduce((total, job) => total + job.count, 0)
  );

  const loadData = async () => {
    loading.value = true;
    try {
      const { data } = await getSkillCatalog({
        keyword: filters.keyword.trim() || undefined,
        jobId: filters.jobId,
        advancement: filters.advancement,
        pageNo: filters.pageNo,
        pageSize: filters.pageSize,
      });
      Object.assign(page, {
        records: data?.records || [],
        jobs: data?.jobs || [],
        pageNo: data?.pageNo || filters.pageNo,
        pageSize: data?.pageSize || filters.pageSize,
        total: data?.total || 0,
        loaded: data?.loaded ?? true,
        message: data?.message || '',
      });
    } catch {
      Object.assign(page, {
        records: [],
        jobs: [],
        total: 0,
        loaded: false,
        message: '技能目录接口失败，请确认服务端已重启并重新加载',
      });
    } finally {
      loading.value = false;
    }
  };

  const reloadCatalog = async () => {
    reloading.value = true;
    try {
      await reloadSkillCatalog();
      await loadData();
    } finally {
      reloading.value = false;
    }
  };

  const applySearch = () => {
    filters.pageNo = 1;
    loadData();
  };

  const selectJob = (jobId: number | undefined) => {
    filters.jobId = jobId;
    filters.advancement = undefined;
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
    grid-template-columns: 220px minmax(0, 1fr);
    min-height: calc(100vh - 209px);
  }

  .job-list {
    padding: 10px;
    border-right: 1px solid var(--color-neutral-3);
    background: var(--color-fill-1);
    overflow-y: auto;
    max-height: calc(100vh - 209px);

    button {
      display: flex;
      width: 100%;
      min-height: 32px;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 6px 10px;
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

  .job-group {
    margin-bottom: 8px;

    .group-label {
      padding: 8px 10px 4px;
      font-size: 12px;
      font-weight: 600;
      color: var(--color-text-3);
      text-transform: uppercase;
      letter-spacing: 0.5px;
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

  .skill-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
    align-content: start;
  }

  .skill-card {
    display: flex;
    height: 72px;
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

  .skill-copy {
    flex: 1;
    min-width: 0;

    strong {
      display: -webkit-box;
      overflow: hidden;
      color: var(--color-text-1);
      font-size: 13px;
      line-height: 18px;
      overflow-wrap: anywhere;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 1;
    }

    .skill-id,
    small {
      display: block;
      margin-top: 2px;
      color: var(--color-text-3);
      font-size: 11px;
      line-height: 14px;
    }
  }

  .skill-level {
    flex-shrink: 0;
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

    .job-list {
      display: flex;
      flex-wrap: wrap;
      overflow-x: auto;
      border-right: 0;
      border-bottom: 1px solid var(--color-neutral-3);
      max-height: none;

      button {
        width: auto;
        min-width: 100px;
        flex: 0 0 auto;
      }

      .job-group {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        margin-bottom: 0;

        .group-label {
          padding: 6px 8px;
        }
      }
    }

    .skill-grid {
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    }
  }

  @media (max-width: 520px) {
    .catalog-results {
      padding: 10px;
    }

    .skill-grid {
      grid-template-columns: 1fr;
    }

    .pagination-row {
      overflow-x: auto;
      justify-content: flex-start;
    }
  }
</style>
