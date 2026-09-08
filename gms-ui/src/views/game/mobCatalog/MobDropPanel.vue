<template>
  <div class="mob-drop-panel">
    <div class="panel-header">
      <h3>{{ mob.name }} 的掉落物</h3>
      <a-button type="primary" size="small" @click="showAddDrop = true">
        <template #icon><icon-plus /></template>
        添加掉落物
      </a-button>
    </div>

    <!-- 类别筛选标签 -->
    <div class="category-filter">
      <a-space wrap>
        <a-tag
          v-for="cat in availableCategories"
          :key="cat"
          :color="selectedCategory === cat ? 'blue' : ''"
          :checkable="true"
          :checked="selectedCategory === cat"
          @click="toggleCategory(cat)"
        >
          {{ cat }} ({{ getCategoryCount(cat) }})
        </a-tag>
        <a-tag
          :color="selectedCategory === '' ? 'blue' : ''"
          :checkable="true"
          :checked="selectedCategory === ''"
          @click="selectedCategory = ''"
        >
          全部 ({{ drops.length }})
        </a-tag>
      </a-space>
    </div>

    <a-spin :loading="loading" tip="">
      <div v-if="filteredDrops.length" class="drop-list">
        <div v-for="drop in filteredDrops" :key="drop.id" class="drop-item">
          <div class="drop-info">
            <div class="item-header">
              <a-tag :color="getCategoryColor(drop.itemCategory)" size="small">
                {{ drop.itemCategory }}
              </a-tag>
              <span v-if="drop.itemId === 0" class="item-name gold-drop">金币</span>
              <span v-else class="item-name">{{ drop.itemName || `未知物品 ${drop.itemId}` }}</span>
            </div>
            <span v-if="drop.itemId > 0" class="item-id">ID: {{ drop.itemId }}</span>
          </div>
          <div class="drop-details">
            <span v-if="drop.itemId === 0">数量: {{ drop.minimumQuantity }}{{ drop.maximumQuantity > drop.minimumQuantity ? ` - ${drop.maximumQuantity}` : '' }} 金币</span>
            <span v-else>数量: {{ drop.minimumQuantity }}{{ drop.maximumQuantity > drop.minimumQuantity ? ` - ${drop.maximumQuantity}` : '' }}</span>
            <span>概率: {{ formatChance(drop.chance) }}</span>
            <span v-if="drop.questId">任务: {{ drop.questName || drop.questId }}</span>
          </div>
          <a-button
            type="text"
            size="mini"
            status="danger"
            @click="handleDeleteDrop(drop.id)"
          >
            <template #icon><icon-delete /></template>
          </a-button>
        </div>
      </div>
      <a-empty v-else description="暂无掉落物" />
    </a-spin>

    <!-- 添加掉落物对话框 -->
    <a-modal
      v-model:visible="showAddDrop"
      title="添加掉落物"
      @ok="handleAddDrop"
      @cancel="showAddDrop = false"
    >
      <a-form :model="newDrop" layout="vertical">
        <a-form-item label="物品ID" required>
          <a-input-number v-model="newDrop.itemId" :min="1" placeholder="输入物品ID" />
        </a-form-item>
        <a-form-item label="最小数量">
          <a-input-number v-model="newDrop.minimumQuantity" :min="1" />
        </a-form-item>
        <a-form-item label="最大数量">
          <a-input-number v-model="newDrop.maximumQuantity" :min="1" />
        </a-form-item>
        <a-form-item label="概率 (1/1000000)">
          <a-input-number v-model="newDrop.chance" :min="1" :max="1000000" placeholder="1000000 = 100%" />
        </a-form-item>
        <a-form-item label="任务ID (可选)">
          <a-input-number v-model="newDrop.questId" :min="0" placeholder="0表示无任务限制" />
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model="newDrop.comments" placeholder="可选备注" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
  import { ref, onMounted, watch, computed } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { MobCatalogItem, MobDropItem, AddDropParams, getMobDrops, addMobDrop, deleteMobDrop } from '@/api/mobCatalog';

  const props = defineProps<{
    mob: MobCatalogItem;
  }>();

  const emit = defineEmits<{
    (e: 'close'): void;
  }>();

  const loading = ref(false);
  const drops = ref<MobDropItem[]>([]);
  const showAddDrop = ref(false);
  const selectedCategory = ref('');
  const newDrop = ref<AddDropParams>({
    itemId: 0,
    minimumQuantity: 1,
    maximumQuantity: 1,
    chance: 1000000,
    questId: 0,
    comments: '',
  });

  // 计算可用的类别列表
  const availableCategories = computed(() => {
    const categories = new Set(drops.value.map(d => d.itemCategory));
    return Array.from(categories).sort();
  });

  // 按类别筛选后的掉落物
  const filteredDrops = computed(() => {
    if (!selectedCategory.value) {
      return drops.value;
    }
    return drops.value.filter(d => d.itemCategory === selectedCategory.value);
  });

  // 获取指定类别的掉落物数量
  const getCategoryCount = (category: string) => {
    return drops.value.filter(d => d.itemCategory === category).length;
  };

  // 切换类别筛选
  const toggleCategory = (category: string) => {
    if (selectedCategory.value === category) {
      selectedCategory.value = '';
    } else {
      selectedCategory.value = category;
    }
  };

  // 获取类别对应的颜色
  const getCategoryColor = (category: string) => {
    const colorMap: Record<string, string> = {
      '装备': 'red',
      '消耗': 'blue',
      '设置': 'green',
      '其他': 'orange',
      '特殊': 'purple',
      '金币': 'gold',
      '未知': 'gray',
    };
    return colorMap[category] || 'gray';
  };

  const loadDrops = async () => {
    loading.value = true;
    try {
      const { data } = await getMobDrops(props.mob.id);
      drops.value = data;
    } catch (error) {
      console.error('Failed to load drops:', error);
    } finally {
      loading.value = false;
    }
  };

  const formatChance = (chance: number) => {
    if (chance >= 1000000) return '100%';
    return `${(chance / 10000).toFixed(2)}%`;
  };

  const handleAddDrop = async () => {
    if (!newDrop.value.itemId) {
      Message.error('请输入物品ID');
      return;
    }
    try {
      await addMobDrop(props.mob.id, newDrop.value);
      Message.success('添加成功');
      showAddDrop.value = false;
      newDrop.value = {
        itemId: 0,
        minimumQuantity: 1,
        maximumQuantity: 1,
        chance: 1000000,
        questId: 0,
        comments: '',
      };
      await loadDrops();
    } catch (error) {
      Message.error('添加失败');
    }
  };

  const handleDeleteDrop = async (dropId: number) => {
    try {
      await deleteMobDrop(dropId);
      Message.success('删除成功');
      await loadDrops();
    } catch (error) {
      Message.error('删除失败');
    }
  };

  watch(() => props.mob, () => {
    selectedCategory.value = '';
    loadDrops();
  });

  onMounted(loadDrops);
</script>

<style scoped lang="less">
  .mob-drop-panel {
    width: 100%;
    max-height: 600px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid var(--color-neutral-3);

    h3 {
      margin: 0;
      font-size: 16px;
      color: var(--color-text-1);
    }
  }

  .category-filter {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-neutral-3);
    background: var(--color-bg-1);
  }

  .drop-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
  }

  .drop-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    margin-bottom: 8px;
    border: 1px solid var(--color-neutral-3);
    border-radius: 6px;
    background: var(--color-bg-2);

    &:hover {
      border-color: var(--color-primary-light-4);
    }
  }

  .drop-info {
    flex: 1;
    min-width: 0;

    .item-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
    }

    .item-name {
      font-weight: 500;
      color: var(--color-text-1);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;

      &.gold-drop {
        color: #faad14;
        font-weight: 600;
      }
    }

    .item-id {
      font-size: 12px;
      color: var(--color-text-3);
    }
  }

  .drop-details {
    display: flex;
    gap: 16px;
    font-size: 13px;
    color: var(--color-text-2);

    span {
      white-space: nowrap;
    }
  }
</style>
