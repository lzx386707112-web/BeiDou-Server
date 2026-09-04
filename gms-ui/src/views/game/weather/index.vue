<template>
  <div class="container">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('menu.game.weather')">
      <div class="status-band">
        <div class="status-item">
          <span>{{ $t('weather.state.time') }}</span>
          <strong>{{ formattedTime }}</strong>
        </div>
        <div class="status-item">
          <span>{{ $t('weather.state.night') }}</span>
          <strong>{{ Math.round((state?.nightLevel || 0) * 100) }}%</strong>
        </div>
        <div class="status-item">
          <span>{{ $t('weather.state.mode') }}</span>
          <a-tag
            :color="
              state?.weatherOverridden || state?.timeFrozen
                ? 'orangered'
                : 'green'
            "
          >
            {{
              state?.weatherOverridden || state?.timeFrozen
                ? $t('weather.mode.override')
                : $t('weather.mode.auto')
            }}
          </a-tag>
          <small v-if="state?.weatherOverridden || state?.timeFrozen">{{
            overrideDetail
          }}</small>
          <small v-else>{{
            $t('weather.state.nextRoll', { seconds: state?.nextRollInSec || 0 })
          }}</small>
        </div>
        <div class="status-item">
          <span>{{ $t('weather.state.online') }}</span>
          <strong>{{ state?.onlinePlayers || 0 }}</strong>
        </div>
        <a-tooltip :content="$t('weather.action.refresh')">
          <a-button :loading="loading" @click="loadAll"
            ><template #icon><icon-refresh /></template
          ></a-button>
        </a-tooltip>
      </div>

      <a-divider />
      <h3>{{ $t('weather.override.title') }}</h3>
      <a-space wrap size="medium">
        <a-select
          v-model="overrideForm.profile"
          allow-clear
          :placeholder="$t('weather.override.profile')"
          class="control"
        >
          <a-option
            v-for="profile in profiles"
            :key="profile"
            :value="profile"
            >{{ profileLabel(profile) }}</a-option
          >
        </a-select>
        <a-input-number
          v-model="overrideForm.minuteOfDay"
          allow-clear
          :min="0"
          :max="1439"
          :placeholder="$t('weather.override.minute')"
          class="control"
        />
        <a-input-number
          v-model="overrideForm.durationMinutes"
          :min="1"
          :max="1440"
          :placeholder="$t('weather.override.duration')"
          class="control"
        />
        <a-button type="primary" :loading="acting" @click="applyOverride"
          ><template #icon><icon-thunderbolt /></template
          >{{ $t('weather.action.apply') }}</a-button
        >
        <a-button :loading="acting" @click="restoreAuto"
          ><template #icon><icon-undo /></template
          >{{ $t('weather.action.auto') }}</a-button
        >
        <a-button :loading="acting" @click="broadcastNow"
          ><template #icon><icon-send /></template
          >{{ $t('weather.action.broadcast') }}</a-button
        >
      </a-space>

      <a-divider />
      <h3>{{ $t('weather.config.title') }}</h3>
      <a-form
        :model="configForm"
        layout="vertical"
        @submit-success="saveConfig"
      >
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12" :lg="4"
            ><a-form-item :label="$t('weather.config.enabled')"
              ><a-switch v-model="configForm.enabled" /></a-form-item
          ></a-col>
          <a-col :xs="24" :sm="12" :lg="5"
            ><a-form-item :label="$t('weather.config.dayHours')"
              ><a-input-number
                v-model="configForm.dayHours"
                :min="1"
                :max="24"
                :step="0.5" /></a-form-item
          ></a-col>
          <a-col :xs="24" :sm="12" :lg="5"
            ><a-form-item :label="$t('weather.config.changeMinutes')"
              ><a-input-number
                v-model="configForm.changeMinutes"
                :min="1"
                :max="1440" /></a-form-item
          ></a-col>
          <a-col :xs="24" :sm="12" :lg="5"
            ><a-form-item :label="$t('weather.config.holdMinutes')"
              ><a-input-number
                v-model="configForm.holdMinutes"
                :min="1"
                :max="1440" /></a-form-item
          ></a-col>
          <a-col :xs="24" :sm="12" :lg="5"
            ><a-form-item :label="$t('weather.config.rainbowSeconds')"
              ><a-input-number
                v-model="configForm.rainbowSeconds"
                :min="0"
                :max="3600" /></a-form-item
          ></a-col>
        </a-row>
        <a-button html-type="submit" type="primary" :loading="saving"
          ><template #icon><icon-save /></template
          >{{ $t('weather.action.save') }}</a-button
        >
      </a-form>

      <a-divider />
      <h3>{{ $t('weather.regions.title') }}</h3>
      <a-table
        row-key="region"
        :data="regions"
        :loading="loading"
        :pagination="{ pageSize: 15, showTotal: true }"
        :scroll="{ x: 960 }"
        :bordered="{ cell: true }"
      >
        <template #columns>
          <a-table-column
            :title="$t('weather.regions.region')"
            data-index="region"
            :width="190"
          />
          <a-table-column :title="$t('weather.regions.current')" :width="120"
            ><template #cell="{ record }"
              ><a-tag>{{
                profileLabel(record.currentProfile)
              }}</a-tag></template
            ></a-table-column
          >
          <a-table-column :title="$t('weather.regions.forced')" :width="130"
            ><template #cell="{ record }">{{
              record.forcedProfile
                ? profileLabel(record.forcedProfile)
                : $t('weather.mode.auto')
            }}</template></a-table-column
          >
          <a-table-column :title="$t('weather.regions.tint')" :width="120"
            ><template #cell="{ record }"
              ><span
                class="swatch"
                :style="{ backgroundColor: tintHex(record.nightTint) }"
              ></span
              >{{ tintHex(record.nightTint) }}</template
            ></a-table-column
          >
          <a-table-column
            :title="$t('weather.regions.palette')"
            data-index="paletteId"
            :width="90"
            align="center"
          />
          <a-table-column :title="$t('weather.regions.weights')" :width="290"
            ><template #cell="{ record }"
              ><span class="weights">{{
                weightsSummary(record.weights)
              }}</span></template
            ></a-table-column
          >
          <a-table-column
            :title="$t('weather.regions.operation')"
            :width="90"
            fixed="right"
            align="center"
            ><template #cell="{ record }"
              ><a-button type="text" @click="openRegion(record)"
                ><template #icon><icon-edit /></template></a-button></template
          ></a-table-column>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:visible="regionVisible"
      :title="editingRegion?.region"
      :width="'min(760px, calc(100vw - 32px))'"
      :ok-loading="savingRegion"
      @ok="saveRegion"
    >
      <a-form v-if="editingRegion" :model="regionForm" layout="vertical">
        <a-row :gutter="16">
          <a-col :xs="24" :sm="12"
            ><a-form-item :label="$t('weather.regions.forced')"
              ><a-select v-model="regionForm.forcedProfile" allow-clear
                ><a-option
                  v-for="profile in profiles"
                  :key="profile"
                  :value="profile"
                  >{{ profileLabel(profile) }}</a-option
                ></a-select
              ></a-form-item
            ></a-col
          >
          <a-col :xs="24" :sm="12"
            ><a-form-item :label="$t('weather.regions.palette')"
              ><a-input-number
                v-model="regionForm.paletteId"
                :min="0"
                :max="26" /></a-form-item
          ></a-col>
          <a-col :xs="24" :sm="12"
            ><a-form-item :label="$t('weather.regions.tint')"
              ><a-input v-model="regionForm.tint" placeholder="#4A5A8C"
                ><template #prefix
                  ><span
                    class="swatch"
                    :style="{ backgroundColor: regionForm.tint }"
                  ></span></template></a-input></a-form-item
          ></a-col>
        </a-row>
        <a-row :gutter="16"
          ><a-col
            v-for="(profile, index) in profiles"
            :key="profile"
            :xs="12"
            :sm="8"
            ><a-form-item :label="profileLabel(profile)"
              ><a-input-number
                v-model="regionForm.weights[index]"
                :min="0"
                :max="1000"
                :step="0.1" /></a-form-item></a-col
        ></a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, reactive, ref } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { useI18n } from 'vue-i18n';
  import useLoading from '@/hooks/loading';
  import {
    WEATHER_PROFILES,
    WeatherRegion,
    broadcastWeather,
    clearWeatherOverride,
    getWeatherConfig,
    getWeatherRegions,
    getWeatherState,
    setWeatherOverride,
    updateWeatherConfig,
    updateWeatherRegion,
  } from '@/api/weather';

  const { t } = useI18n();
  const { loading, setLoading } = useLoading(false);
  const profiles = WEATHER_PROFILES;
  const state = ref<Awaited<ReturnType<typeof getWeatherState>>['data']>();
  const regions = ref<WeatherRegion[]>([]);
  const saving = ref(false);
  const acting = ref(false);
  const savingRegion = ref(false);
  const regionVisible = ref(false);
  const editingRegion = ref<WeatherRegion>();
  const configForm = reactive({
    enabled: true,
    dayHours: 4,
    changeMinutes: 15,
    holdMinutes: 60,
    rainbowSeconds: 180,
  });
  const overrideForm = reactive<{
    profile?: string;
    minuteOfDay?: number;
    durationMinutes: number;
  }>({ durationMinutes: 60 });
  const regionForm = reactive<{
    forcedProfile?: string;
    weights: number[];
    tint: string;
    paletteId: number;
  }>({ weights: [], tint: '#4A5A8C', paletteId: 26 });
  const profileLabel = (profile: string) => t(`weather.profile.${profile}`);
  const formattedTime = computed(() => {
    const minute = state.value?.minuteOfDay || 0;
    return `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(
      minute % 60
    ).padStart(2, '0')}`;
  });
  const overrideDetail = computed(() =>
    t('weather.state.remaining', {
      profile: state.value?.overrideProfile
        ? profileLabel(state.value.overrideProfile)
        : t('weather.override.timeOnly'),
      seconds: state.value?.overrideRemainingSec || 0,
    })
  );
  const tintHex = (value: number) =>
    `#${value.toString(16).padStart(6, '0').toUpperCase()}`;
  const weightsSummary = (values: number[]) =>
    values
      .map((value, index) => `${profileLabel(profiles[index])} ${value}`)
      .join(' / ');

  const loadAll = async () => {
    setLoading(true);
    try {
      const [stateRes, configRes, regionsRes] = await Promise.all([
        getWeatherState(),
        getWeatherConfig(),
        getWeatherRegions(),
      ]);
      state.value = stateRes.data;
      regions.value = regionsRes.data;
      const value = configRes.data;
      configForm.enabled = value.enabled;
      configForm.dayHours = value.dayLengthMs / 3600000;
      configForm.changeMinutes = value.changeIntervalMs / 60000;
      configForm.holdMinutes = value.overrideHoldMs / 60000;
      configForm.rainbowSeconds = value.rainbowDurationSec;
      overrideForm.durationMinutes = configForm.holdMinutes;
    } finally {
      setLoading(false);
    }
  };
  const refreshRuntime = async () => {
    const [stateRes, regionsRes] = await Promise.all([
      getWeatherState(),
      getWeatherRegions(),
    ]);
    state.value = stateRes.data;
    regions.value = regionsRes.data;
  };
  const saveConfig = async () => {
    saving.value = true;
    try {
      const { data } = await updateWeatherConfig({
        enabled: configForm.enabled,
        dayLengthMs: Math.round(configForm.dayHours * 3600000),
        changeIntervalMs: Math.round(configForm.changeMinutes * 60000),
        overrideHoldMs: Math.round(configForm.holdMinutes * 60000),
        rainbowDurationSec: Math.round(configForm.rainbowSeconds),
      });
      Message.success(t('weather.message.saved', { count: data }));
      await refreshRuntime();
    } finally {
      saving.value = false;
    }
  };
  const applyOverride = async () => {
    if (!overrideForm.profile && overrideForm.minuteOfDay === undefined) {
      Message.warning(t('weather.message.overrideRequired'));
      return;
    }
    acting.value = true;
    try {
      const { data } = await setWeatherOverride({ ...overrideForm });
      Message.success(t('weather.message.broadcast', { count: data }));
      await refreshRuntime();
    } finally {
      acting.value = false;
    }
  };
  const restoreAuto = async () => {
    acting.value = true;
    try {
      const { data } = await clearWeatherOverride();
      Message.success(t('weather.message.auto', { count: data }));
      await refreshRuntime();
    } finally {
      acting.value = false;
    }
  };
  const broadcastNow = async () => {
    acting.value = true;
    try {
      const { data } = await broadcastWeather();
      Message.success(t('weather.message.broadcast', { count: data }));
    } finally {
      acting.value = false;
    }
  };
  const openRegion = (region: WeatherRegion) => {
    editingRegion.value = region;
    regionForm.forcedProfile = region.forcedProfile;
    regionForm.weights = [...region.weights];
    regionForm.tint = tintHex(region.nightTint);
    regionForm.paletteId = region.paletteId;
    regionVisible.value = true;
  };
  const saveRegion = async () => {
    if (!editingRegion.value || !/^#[0-9a-fA-F]{6}$/.test(regionForm.tint)) {
      Message.warning(t('weather.message.tint'));
      return false;
    }
    if (regionForm.weights.reduce((sum, value) => sum + (value || 0), 0) <= 0) {
      Message.warning(t('weather.message.weights'));
      return false;
    }
    savingRegion.value = true;
    try {
      const { data } = await updateWeatherRegion(editingRegion.value.region, {
        forcedProfile: regionForm.forcedProfile,
        weights: [...regionForm.weights],
        nightTint: Number.parseInt(regionForm.tint.slice(1), 16),
        paletteId: regionForm.paletteId,
      });
      Message.success(t('weather.message.saved', { count: data }));
      regionVisible.value = false;
      await refreshRuntime();
      return true;
    } finally {
      savingRegion.value = false;
    }
  };
  onMounted(loadAll);
</script>

<style scoped lang="less">
  .container {
    padding: 0 20px 20px;
  }
  .status-band {
    display: grid;
    grid-template-columns: repeat(4, minmax(120px, 1fr)) auto;
    gap: 20px;
    align-items: center;
  }
  .status-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: var(--color-text-3);
  }
  .status-item strong {
    color: var(--color-text-1);
    font-size: 20px;
  }
  .status-item small {
    color: var(--color-text-3);
  }
  h3 {
    margin: 0 0 16px;
    font-size: 16px;
    letter-spacing: 0;
  }
  .control {
    width: 190px;
  }
  .swatch {
    display: inline-block;
    width: 16px;
    height: 16px;
    margin-right: 8px;
    vertical-align: -3px;
    border: 1px solid var(--color-border-2);
  }
  .weights {
    color: var(--color-text-2);
    white-space: normal;
    line-height: 1.7;
  }
  @media (max-width: 767px) {
    .container {
      padding: 0 12px 16px;
    }
    .status-band {
      grid-template-columns: repeat(2, minmax(100px, 1fr));
    }
    .control {
      width: 100%;
    }
  }
</style>
