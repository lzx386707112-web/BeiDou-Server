<template>
  <div class="skill-detail">
    <div class="skill-header">
      <SkillIcon :skill-id="skill.id" />
      <div class="skill-title">
        <strong>{{ skill.name || `技能 ${skill.id}` }}</strong>
        <span>ID: {{ skill.id }}</span>
        <small>{{ skill.jobName }}</small>
      </div>
    </div>

    <div class="skill-meta">
      <span>最高等级 {{ skill.maxLevel }}</span>
      <span v-if="advancement > 0">{{ advancement }}转</span>
      <span>冷却 {{ cooldownText }}</span>
      <span>MP {{ mpText }}</span>
    </div>

    <div v-if="skill.desc" class="skill-desc" v-html="formatDesc(skill.desc)"></div>

    <div v-if="attrRows.length > 0" class="skill-attrs">
      <div class="section-title">技能属性</div>
      <div class="attr-grid">
        <div v-for="row in attrRows" :key="row.key">
          <span>{{ row.label }}</span>
          <strong>{{ row.value }}</strong>
        </div>
      </div>
    </div>

    <div v-if="skill.levelDescs && skill.levelDescs.length > 0" class="skill-levels">
      <div class="section-title">等级效果</div>
      <div class="level-list">
        <div v-for="(desc, index) in skill.levelDescs" :key="index" class="level-item">
          <span class="level-num">Lv.{{ index + 1 }}</span>
          <span class="level-desc">{{ desc }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { SkillCatalogItem } from '@/api/skillCatalog';
  import SkillIcon from './SkillIcon.vue';

  const props = defineProps<{
    skill: SkillCatalogItem;
  }>();

  const ATTR_LABELS: Record<string, string> = {
    elemAttr: '元素属性',
    skillType: '技能类型',
    cooltime: '冷却时间',
    mpCon: 'MP消耗',
    time: '持续时间',
    damage: '伤害',
    attackCount: '攻击次数',
    mobCount: '攻击目标数',
  };

  const advancement = computed(() => {
    const jobId = props.skill.jobId;
    if (jobId % 1000 === 0) return 0;
    if (jobId % 100 === 0) return 1;
    if (jobId % 10 === 0) return 2;
    if (jobId % 10 === 1) return 3;
    if (jobId % 10 === 2) return 4;
    return 0;
  });

  const cooldownText = computed(() => formatSeconds(props.skill.attributes?.cooltime));
  const mpText = computed(() => {
    const value = props.skill.attributes?.mpCon;
    if (value === null || value === undefined || value === '') return '无';
    return String(value);
  });

  const attrRows = computed(() => {
    const attributes = props.skill.attributes || {};
    return Object.keys(attributes).map((key) => ({
      key,
      label: ATTR_LABELS[key] || key,
      value: formatAttrValue(key, attributes[key]),
    }));
  });

  const formatDesc = (desc: string) => desc.replace(/\n/g, '<br>');

  const formatSeconds = (value: unknown) => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return '无';
    return `${n} 秒`;
  };

  const formatAttrValue = (key: string, value: unknown) => {
    if (value === null || value === undefined || value === '') return '-';
    if (key === 'cooltime' || key === 'time') {
      return formatSeconds(value);
    }
    if (key === 'skillType') {
      const n = Number(value);
      if (n === 0) return '普通';
      if (n === 1) return '物攻';
      if (n === 2) return '魔法';
      return String(value);
    }
    return String(value);
  };
</script>

<style scoped lang="less">
  .skill-detail {
    width: 360px;
    max-width: 520px;
    padding: 14px;
    color: #f4f7fb;
    border: 1px solid #6f8196;
    border-radius: 6px;
    background: #17202a;
    box-shadow: 0 10px 28px rgb(0 0 0 / 34%);
  }

  .skill-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid #3d4a58;
  }

  .skill-title {
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

  .skill-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    margin-top: 10px;
    color: #78dba9;
    font-size: 12px;
  }

  .skill-desc {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #303c49;
    color: #aebdcb;
    font-size: 12px;
    line-height: 18px;
  }

  .skill-attrs,
  .skill-levels {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #303c49;
  }

  .section-title {
    margin-bottom: 7px;
    color: #96a8ba;
    font-size: 11px;
  }

  .attr-grid {
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

  .level-list {
    max-height: 240px;
    overflow-y: auto;
  }

  .level-item {
    display: flex;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px solid #303c49;

    &:last-child {
      border-bottom: 0;
    }
  }

  .level-num {
    flex-shrink: 0;
    width: 42px;
    color: #7eb6ff;
    font-size: 12px;
    font-weight: 500;
  }

  .level-desc {
    flex: 1;
    color: #aebdcb;
    font-size: 12px;
    line-height: 1.4;
  }
</style>
