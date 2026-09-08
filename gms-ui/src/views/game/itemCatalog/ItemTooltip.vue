<template>
  <div class="item-tooltip">
    <div class="tooltip-header">
      <ItemIcon :item-id="item.id" :alt="item.name" />
      <div class="title-block">
        <strong>{{ item.name }}</strong>
        <span>{{ item.id }}</span>
        <small>{{ categoryName(item.category) }}</small>
      </div>
    </div>

    <div v-if="item.description" class="description">{{ item.description }}</div>

    <div v-if="Object.keys(item.specs).length > 0" class="spec-section">
      <div class="section-title">物品属性</div>
      <div class="spec-grid">
        <div v-for="(value, key) in item.specs" :key="key">
          <span>{{ specName(key) }}</span>
          <strong>{{ formatSpecValue(key, value) }}</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ItemCatalogItem } from '@/api/itemCatalog';
  import ItemIcon from './ItemIcon.vue';

  const props = defineProps<{ item: ItemCatalogItem }>();

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

  const specName = (key: string) => {
    const names: Record<string, string> = {
      price: '价格',
      slotMax: '最大数量',
      hp: '恢复HP',
      mp: '恢复MP',
      attack: '攻击力',
      magic: '魔法力',
      defense: '防御力',
      speed: '速度',
      jump: '跳跃力',
      reqLevel: '需要等级',
      reqJob: '需要职业',
      cash: '现金物品',
    };
    return names[key] || key;
  };

  const formatSpecValue = (key: string, value: any) => {
    if (key === 'price') {
      return `${Number(value).toLocaleString()} 金币`;
    }
    if (key === 'cash') {
      return value === 1 ? '是' : '否';
    }
    return String(value);
  };
</script>

<style scoped lang="less">
  .item-tooltip {
    width: 300px;
    padding: 14px;
    color: #f4f7fb;
    border: 1px solid #6f8196;
    border-radius: 6px;
    background: #17202a;
    box-shadow: 0 10px 28px rgb(0 0 0 / 34%);
  }

  .tooltip-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid #3d4a58;
  }

  .title-block {
    min-width: 0;

    strong,
    span,
    small {
      display: block;
      letter-spacing: 0;
    }

    strong {
      overflow-wrap: anywhere;
      color: #fff4ad;
      font-size: 15px;
      line-height: 20px;
    }

    span,
    small {
      margin-top: 2px;
      color: #b8c6d6;
      font-size: 12px;
    }
  }

  .description {
    margin: 0;
    padding-top: 10px;
    color: #aebdcb;
    border-top: 1px solid #303c49;
    font-size: 12px;
    line-height: 18px;
    white-space: pre-wrap;
  }

  .spec-section {
    padding: 9px 0;
    border-top: 1px solid #303c49;
  }

  .section-title {
    margin-bottom: 7px;
    color: #96a8ba;
    font-size: 11px;
  }

  .spec-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 5px 18px;

    div {
      display: flex;
      min-width: 0;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
    }

    span {
      overflow: hidden;
      color: #d4dde7;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    strong {
      color: #78dba9;
    }
  }
</style>
