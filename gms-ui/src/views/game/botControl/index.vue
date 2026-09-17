<template>
  <div class="container">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('menu.game.botControl')">
      <div class="status-band">
        <div class="status-item">
          <span>{{ $t('botControl.state.market') }}</span>
          <strong>{{ marketStatusLabel }}</strong>
        </div>
        <div class="status-item">
          <span>{{ $t('botControl.state.active') }}</span>
          <strong>{{ state?.activeBots || 0 }}</strong>
        </div>
        <div class="status-item">
          <span>{{ $t('botControl.state.director') }}</span>
          <strong>{{ state?.marketDirectorBots || 0 }}</strong>
        </div>
        <div class="status-item">
          <span>{{ $t('botControl.state.entrance') }}</span>
          <strong>{{ state?.marketEntranceBots || 0 }}</strong>
        </div>
        <div class="status-item">
          <span>{{ $t('botControl.state.online') }}</span>
          <strong>{{ state?.onlinePlayers || 0 }}</strong>
        </div>
        <a-space>
          <a-button type="primary" :loading="starting" @click="startMarket">
            {{ $t('botControl.action.start') }}
          </a-button>
          <a-tooltip :content="$t('botControl.action.refresh')">
            <a-button :loading="loading" @click="loadAll">
              <template #icon><icon-refresh /></template>
            </a-button>
          </a-tooltip>
        </a-space>
      </div>

      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="market" :title="$t('botControl.tab.market')"> </a-tab-pane>
        <a-tab-pane
          key="appearance"
          :title="$t('botControl.tab.appearance')"
        ></a-tab-pane>
        <a-tab-pane
          key="environment"
          :title="$t('botControl.tab.environment')"
        ></a-tab-pane>
        <a-tab-pane key="party" :title="$t('botControl.tab.party')"></a-tab-pane>
      </a-tabs>

      <a-alert v-if="activeTab === 'party'" type="info">
        {{ $t('botControl.party.soon') }}
      </a-alert>
      <a-form v-else layout="vertical">
        <a-row :gutter="16">
          <a-col
            v-for="field in activeFields"
            :key="field.code"
            :xs="24"
            :sm="12"
          >
            <a-form-item :label="fieldLabel(field.code)">
              <a-switch
                v-if="isBoolean(field)"
                :model-value="field.value === 'true'"
                @change="(checked: boolean) => (field.value = String(checked))"
              />
              <a-input-number
                v-else
                v-model="field.numberValue"
                :min="1"
                :max="60000"
                hide-button
                @change="(value: number) => (field.value = String(value ?? 1))"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-button type="primary" :loading="saving" @click="saveAll">
          {{ $t('botControl.action.save') }}
        </a-button>
      </a-form>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { Message } from '@arco-design/web-vue';
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    BotControlField,
    BotControlState,
    getBotControlConfig,
    getBotControlState,
    startMarketBots,
    updateBotControlConfig,
  } from '@/api/botControl';

  interface EditableField extends BotControlField {
    numberValue?: number;
  }

  const { t } = useI18n();
  const loading = ref(false);
  const saving = ref(false);
  const starting = ref(false);
  const activeTab = ref('market');
  const state = ref<BotControlState>();
  const marketFields = ref<EditableField[]>([]);
  const appearanceFields = ref<EditableField[]>([]);
  const environmentFields = ref<EditableField[]>([]);

  const isBoolean = (field: BotControlField) =>
    field.clazz === 'java.lang.Boolean';

  const fieldLabel = (code: string) => {
    const key = `botControl.field.${code}`;
    const label = t(key);
    return label === key ? code : label;
  };

  const toEditable = (fields: BotControlField[] = []) =>
    fields.map((field) => ({
      ...field,
      numberValue: Number(field.value),
    }));

  const activeFields = computed(() => {
    if (activeTab.value === 'appearance') {
      return appearanceFields.value;
    }
    if (activeTab.value === 'environment') {
      return environmentFields.value;
    }
    return marketFields.value;
  });

  const marketStatusLabel = computed(() => {
    if (state.value?.marketReady) {
      return t('botControl.state.ready');
    }
    if (state.value?.marketStarting) {
      return t('botControl.state.starting');
    }
    return t('botControl.state.empty');
  });

  const loadAll = async () => {
    loading.value = true;
    try {
      const [stateRes, configRes] = await Promise.all([
        getBotControlState(),
        getBotControlConfig(),
      ]);
      state.value = stateRes.data;
      marketFields.value = toEditable(configRes.data.market);
      appearanceFields.value = toEditable(configRes.data.appearance);
      environmentFields.value = toEditable(configRes.data.environment);
    } finally {
      loading.value = false;
    }
  };

  const saveAll = async () => {
    saving.value = true;
    try {
      const payload = [
        ...marketFields.value,
        ...appearanceFields.value,
        ...environmentFields.value,
      ].map((field) => ({
        id: field.id,
        code: field.code,
        clazz: field.clazz,
        value: field.value,
        desc: field.desc,
      }));
      const { data } = await updateBotControlConfig(payload);
      Message.success(t('botControl.message.saved', { count: data }));
      await loadAll();
    } finally {
      saving.value = false;
    }
  };

  const startMarket = async () => {
    starting.value = true;
    try {
      const { data } = await startMarketBots();
      Message.success(t(`botControl.message.start.${data}`));
      await loadAll();
    } finally {
      starting.value = false;
    }
  };

  onMounted(loadAll);
</script>

<style scoped lang="less">
  .container {
    padding: 0 20px 20px;
  }

  .status-band {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
    margin-bottom: 16px;
  }

  .status-item {
    display: flex;
    flex-direction: column;
    min-width: 120px;

    span {
      color: var(--color-text-3);
      font-size: 12px;
    }
  }
</style>
