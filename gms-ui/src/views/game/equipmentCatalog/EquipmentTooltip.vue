<template>
  <div class="equipment-tooltip">
    <div class="tooltip-header">
      <EquipmentIcon :item-id="item.id" :alt="item.name" />
      <div class="title-block">
        <strong>{{ item.name }}</strong>
        <span>{{ item.id }}</span>
        <small>{{ categoryName(item.category) }}</small>
      </div>
    </div>

    <div class="requirement-line">
      <span>{{ $t('equipmentCatalog.require.level') }}</span>
      <strong>{{ stat('reqLevel') }}</strong>
      <span>{{ $t('equipmentCatalog.require.job') }}</span>
      <strong>{{ jobRequirement }}</strong>
    </div>

    <div v-if="requirements.length" class="stat-section">
      <div class="section-title">
        {{ $t('equipmentCatalog.section.requirements') }}
      </div>
      <div class="stat-grid">
        <div v-for="entry in requirements" :key="entry.key">
          <span>{{ statName(entry.key) }}</span>
          <strong>{{ entry.value }}</strong>
        </div>
      </div>
    </div>

    <div v-if="genderRequirement" class="gender-line">
      <span>{{ $t('equipmentCatalog.require.gender') }}</span>
      <strong>{{ genderRequirement }}</strong>
    </div>

    <div v-if="bonuses.length" class="stat-section">
      <div class="section-title">{{
        $t('equipmentCatalog.section.stats')
      }}</div>
      <div class="stat-grid">
        <div v-for="entry in bonuses" :key="entry.key">
          <span>{{ statName(entry.key) }}</span>
          <strong>+{{ entry.value }}</strong>
        </div>
      </div>
    </div>

    <div v-if="stat('tuc')" class="upgrade-line">
      <span>{{ $t('equipmentCatalog.stat.tuc') }}</span>
      <strong>{{ stat('tuc') }}</strong>
    </div>
    <p v-if="item.description" class="description">{{ item.description }}</p>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { EquipmentCatalogItem } from '@/api/equipmentCatalog';
  import EquipmentIcon from './EquipmentIcon.vue';

  const props = defineProps<{ item: EquipmentCatalogItem }>();
  const { t, te } = useI18n();
  const stat = (key: string) => props.item.stats[key] || 0;
  const categoryName = (category: string) =>
    t(`equipmentCatalog.category.${category}`);
  const statName = (key: string) => {
    const translationKey = `equipmentCatalog.stat.${key}`;
    if (te(translationKey)) return t(translationKey);
    return key.startsWith('inc') ? key.slice(3) : key;
  };
  const requirements = computed(() =>
    Object.entries(props.item.stats)
      .filter(
        ([key, value]) =>
          key.startsWith('req') &&
          !['reqLevel', 'reqJob'].includes(key) &&
          value > 0
      )
      .map(([key, value]) => ({ key, value }))
      .filter((entry) => entry.value > 0)
  );
  const bonuses = computed(() =>
    Object.entries(props.item.stats)
      .filter(([key, value]) => key.startsWith('inc') && value !== 0)
      .sort(([left], [right]) => {
        const order = [
          'incSTR',
          'incDEX',
          'incINT',
          'incLUK',
          'incPAD',
          'incMAD',
          'incPDD',
          'incMDD',
          'incMHP',
          'incMMP',
          'incACC',
          'incEVA',
          'incSpeed',
          'incJump',
        ];
        const leftIndex = order.includes(left)
          ? order.indexOf(left)
          : order.length;
        const rightIndex = order.includes(right)
          ? order.indexOf(right)
          : order.length;
        return leftIndex - rightIndex || left.localeCompare(right);
      })
      .map(([key, value]) => ({ key, value }))
  );
  const jobRequirement = computed(() => {
    const value = stat('reqJob');
    if (!value) return t('equipmentCatalog.job.all');
    const jobs = [
      [1, 'warrior'],
      [2, 'magician'],
      [4, 'bowman'],
      [8, 'thief'],
      [16, 'pirate'],
    ] as const;
    return jobs
      .filter(([flag]) => Math.floor(value / flag) % 2 === 1)
      .map(([, key]) => t(`equipmentCatalog.job.${key}`))
      .join(' / ');
  });
  const genderRequirement = computed(() => {
    const value = props.item.stats.gender;
    if (value === undefined || value === 2) return '';
    return t(
      value === 0
        ? 'equipmentCatalog.gender.male'
        : 'equipmentCatalog.gender.female'
    );
  });
</script>

<style scoped lang="less">
  .equipment-tooltip {
    width: 326px;
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

  .requirement-line,
  .upgrade-line {
    display: grid;
    grid-template-columns: auto 1fr auto 1fr;
    gap: 6px 10px;
    align-items: center;
    padding: 10px 0;
    color: #b8c6d6;
    font-size: 12px;

    strong {
      color: #fff;
      text-align: right;
    }
  }

  .gender-line {
    display: flex;
    justify-content: space-between;
    padding: 9px 0;
    color: #b8c6d6;
    border-top: 1px solid #303c49;
    font-size: 12px;

    strong {
      color: #fff;
    }
  }

  .stat-section {
    padding: 9px 0;
    border-top: 1px solid #303c49;
  }

  .section-title {
    margin-bottom: 7px;
    color: #96a8ba;
    font-size: 11px;
  }

  .stat-grid {
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

  .upgrade-line {
    grid-template-columns: 1fr auto;
    border-top: 1px solid #303c49;
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
</style>
