<template>
  <div class="container" :loading="loading">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('menu.dashboard.workplace')">
      <a-card
        class="status-card"
        :title="$t('workplace.gameServer.status')"
        :bordered="false"
      >
        <a-row>
          <a-col>
            {{ $t('workplace.gameServer.currently') }}
            <a-tag v-if="serverStatus === 'running'" color="green" bordered>
              {{ $t('workplace.running') }}
            </a-tag>
            <a-tag v-else color="gray" bordered>
              {{ $t('workplace.stopped') }}
            </a-tag>
          </a-col>
        </a-row>
      </a-card>

      <a-card
        class="control-card"
        :title="$t('workplace.gameServer.serverControl')"
        :bordered="false"
      >
        <a-space class="button-group" :size="16">
          <a-button
            v-for="(btn, index) in serverControlButtons"
            :key="index"
            :loading="loading && btn.action !== 'stop'"
            type="primary"
            :disabled="btn.disabled(serverStatus)"
            :status="btn.status"
            @click="handleButtonClick(btn.action)"
          >
            <template #icon>
              <component :is="btn.icon" />
            </template>
            {{ $t(`workplace.button.${btn.label}`) }}
          </a-button>
        </a-space>
      </a-card>

      <a-card
        class="reload-card"
        :title="$t('workplace.dataReload')"
        :bordered="false"
      >
        <a-space class="button-group" :size="16">
          <a-button
            v-for="(btn, index) in dataReloadButtons"
            :key="index + 'reload'"
            :loading="loading"
            type="primary"
            @click="handleButtonClick(btn.action)"
          >
            <template #icon>
              <component :is="btn.icon" />
            </template>
            {{ $t(`workplace.button.${btn.label}`) }}
          </a-button>
        </a-space>
      </a-card>

      <a-card
        class="operation-card"
        :title="$t('workplace.operationTools')"
        :bordered="false"
      >
        <a-space class="button-group" :size="16">
          <a-button type="primary" @click="broadcastVisible = true">
            <template #icon>
              <icon-notification />
            </template>
            {{ $t('workplace.button.broadcast') }}
          </a-button>
          <a-button type="primary" status="warning" @click="siegeVisible = true">
            <template #icon>
              <icon-thunderbolt />
            </template>
            {{ $t('workplace.button.monsterSiege') }}
          </a-button>
          <a-button
            type="primary"
            status="danger"
            :loading="loading"
            @click="handleClearSiege"
          >
            <template #icon>
              <icon-stop />
            </template>
            {{ $t('workplace.button.clearMonsterSiege') }}
          </a-button>
        </a-space>
      </a-card>

      <!-- 完全停服并退出BAT的确认框 -->
      <a-modal
        v-model:visible="shutdownConfirmVisible"
        class="arco-modal-auto"
        draggable
        @ok="handleShutdownConfirm"
        @cancel="handleShutdownCancel"
      >
        <template #title>
          {{ $t('workplace.button.shutdown') }}
        </template>
        <p>{{ $t('workplace.button.shutdown.confirm') }}</p>
      </a-modal>

      <!-- 重启服务端的确认框 -->
      <a-modal
        v-model:visible="restartConfirmVisible"
        modal-class="arco-modal-auto"
        draggable
        @ok="handleRestartConfirm"
        @cancel="handleRestartCancel"
      >
        <template #title>
          {{ $t('workplace.button.restart') }}
        </template>
        <p>{{ $t('workplace.button.restart.confirm') }}</p>
      </a-modal>

      <!-- 停服倒计时配置框 -->
      <a-modal
        v-model:visible="stopConfigVisible"
        modal-class="arco-modal-auto"
        draggable
        @ok="handleStopConfigOk"
        @cancel="handleStopConfigCancel"
      >
        <template #title>
          {{ $t('workplace.button.stop.config') }}
        </template>
        <a-form :model="stopConfigData" layout="vertical">
          <a-card
            :title="$t('workplace.stop.minutes')"
            :bordered="false"
            style="margin-bottom: 16px"
          >
            <a-row :gutter="[16, 16]">
              <a-col :span="18">
                <a-input-number v-model="stopConfigData.minutes" :min="0" />
              </a-col>
              <a-col :span="6">
                <span style="line-height: 32px; text-align: right">{{
                  $t('workplace.unit.minutes')
                }}</span>
              </a-col>
            </a-row>
          </a-card>

          <a-card :bordered="false" style="margin-bottom: 16px">
            <template #title>
              <div style="display: flex; align-items: center">
                <span>{{ $t('workplace.stop.shutdownMsg') }}</span>
                <a-tooltip :content="$t('workplace.stop.shutdownMsgDefault')">
                  <icon-info-circle style="margin-left: 8px" />
                </a-tooltip>
              </div>
            </template>

            <a-row :gutter="[16, 16]">
              <a-col :span="24">
                <a-textarea v-model="stopConfigData.shutdownMsg" />
              </a-col>
            </a-row>
          </a-card>

          <a-card :title="$t('workplace.stop.messageTypes')" :bordered="false">
            <a-space class="button-group" :size="16">
              <a-checkbox v-model="stopConfigData.showServerMsg">
                {{ $t('workplace.stop.showServerMsg') }}
              </a-checkbox>
              <a-checkbox v-model="stopConfigData.showCenterMsg">
                {{ $t('workplace.stop.showCenterMsg') }}
              </a-checkbox>
              <a-checkbox v-model="stopConfigData.showChatMsg">
                {{ $t('workplace.stop.showChatMsg') }}
              </a-checkbox>
            </a-space>
          </a-card>
        </a-form>
      </a-modal>

      <a-modal
        v-model:visible="broadcastVisible"
        modal-class="arco-modal-auto"
        draggable
        :ok-text="$t('button.submit')"
        :on-before-ok="handleBroadcastOk"
        @cancel="handleBroadcastCancel"
      >
        <template #title>
          {{ $t('workplace.button.broadcast') }}
        </template>
        <a-form :model="broadcastData" layout="vertical">
          <a-form-item :label="$t('workplace.broadcast.message')">
            <a-textarea
              v-model="broadcastData.message"
              :max-length="100"
              show-word-limit
            />
          </a-form-item>
        </a-form>
      </a-modal>

      <a-modal
        v-model:visible="siegeVisible"
        modal-class="arco-modal-auto"
        draggable
        :ok-text="$t('button.submit')"
        :on-before-ok="handleSiegeOk"
        @cancel="handleSiegeCancel"
      >
        <template #title>
          {{ $t('workplace.button.monsterSiege') }}
        </template>
        <a-form :model="siegeData" layout="vertical">
          <a-form-item :label="$t('workplace.siege.monsterIds')">
            <a-textarea
              v-model="siegeData.monsterIds"
              :placeholder="$t('workplace.siege.monsterIds.placeholder')"
              :auto-size="{ minRows: 3, maxRows: 5 }"
            />
          </a-form-item>
          <a-form-item :label="$t('workplace.siege.count')">
            <a-input-number v-model="siegeData.count" :min="1" :max="200" />
          </a-form-item>
          <a-form-item :label="$t('workplace.siege.broadcast')">
            <a-switch v-model="siegeData.broadcast" />
          </a-form-item>
          <a-form-item :label="$t('workplace.siege.message')">
            <a-textarea
              v-model="siegeData.message"
              :disabled="!siegeData.broadcast"
              :max-length="100"
              show-word-limit
            />
          </a-form-item>
        </a-form>
        <a-divider />
        <a-typography-title :heading="6">
          {{ $t('workplace.siege.bossList') }}
        </a-typography-title>
        <a-table
          row-key="id"
          :data="bossOptions"
          :pagination="false"
          :bordered="{ cell: true }"
          size="small"
        >
          <template #columns>
            <a-table-column
              :title="$t('workplace.siege.bossName')"
              data-index="name"
              :width="160"
            />
            <a-table-column
              :title="$t('workplace.siege.bossId')"
              data-index="id"
              :width="110"
            >
              <template #cell="{ record }">
                <a-tag color="arcoblue">{{ record.id }}</a-tag>
              </template>
            </a-table-column>
            <a-table-column
              :title="$t('operation')"
              :width="100"
              align="center"
            >
              <template #cell="{ record }">
                <a-button type="text" size="mini" @click="appendBossId(record.id)">
                  {{ $t('workplace.siege.useBossId') }}
                </a-button>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-modal>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { onMounted, reactive, ref } from 'vue';
  import {
    clearMonsterSiege,
    getServerStatus,
    restartServer,
    sendServerBroadcast,
    shutdown,
    startServer,
    startMonsterSiege,
    stopServer,
  } from '@/api/dashboard';
  import { Message } from '@arco-design/web-vue';
  import useLoading from '@/hooks/loading';
  import {
    reloadEventsByGMCommand,
    reloadMapsByGMCommand,
    reloadPortalsByGMCommand,
  } from '@/api/command';
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();
  const { loading, setLoading } = useLoading(false);
  const serverStatus = ref<'resting' | 'running'>('resting');
  const stopConfigVisible = ref(false);
  const broadcastVisible = ref(false);
  const siegeVisible = ref(false);
  const shutdownConfirmVisible = ref(false); // 新增用于确认关机的模态框可见性控制
  const restartConfirmVisible = ref(false); // 新增用于确认重启的模态框可见性控制
  const stopConfigData = reactive({
    minutes: 0,
    shutdownMsg: '',
    showServerMsg: false,
    showCenterMsg: false,
    showChatMsg: false,
  });
  const broadcastData = reactive({
    message: '',
  });
  const siegeData = reactive({
    monsterIds: '',
    count: 1,
    broadcast: true,
    message: '怪物攻城开始！请前往自由市场入口迎战！',
  });
  const bossOptions = [
    { name: '闹钟王', id: 8500001 },
    { name: '皮亚奴斯', id: 8510000 },
    { name: '蝙蝠怪巴洛古', id: 8830000 },
    { name: '扎昆主体', id: 8800002 },
    { name: '进阶扎昆主体', id: 8800102 },
    { name: '暗黑龙王', id: 8810018 },
    { name: '混沌暗黑龙王', id: 8810118 },
    { name: '品克缤', id: 8820001 },
    { name: '希纳斯', id: 8850011 },
    { name: '班·雷昂', id: 8840000 },
    { name: '阿卡伊勒', id: 8860000 },
    { name: '进阶皮埃尔', id: 8900000 },
    { name: '进阶半半', id: 8910000 },
    { name: '混沌血腥女王', id: 8920000 },
    { name: '进阶贝伦', id: 8930000 },
    { name: '愤怒的心疤狮王', id: 9420549 },
    { name: '愤怒的暴力熊', id: 9420544 },
    { name: '克雷塞尔', id: 9420522 },
    { name: '泰国六手邪神', id: 9420014 },
    { name: '武林妖僧', id: 9600025 },
    { name: '贝尔加莫特', id: 9400263 },
    { name: '努克斯', id: 9400266 },
    { name: '都纳斯', id: 9400270 },
    { name: '尼贝隆', id: 9400271 },
    { name: '欧碧拉', id: 9400289 },
    { name: '再生都纳斯', id: 9400294 },
    { name: '大头老板', id: 9400300 },
    { name: '天皇', id: 9400408 },
    { name: '天皇蟾蜍', id: 9400409 },
    { name: '钻机', id: 9600087 },
    { name: '天魔僵尸', id: 9600318 },
  ];

  const serverControlButtons = [
    {
      label: 'start',
      action: 'start',
      disabled: (status: 'resting' | 'running') => status === 'running',
      status: 'success' as const,
      icon: 'icon-play-arrow-fill',
    },
    {
      label: 'stop',
      action: 'stop',
      disabled: (status: 'resting' | 'running') => status === 'resting',
      status: 'danger' as const,
      icon: 'icon-stop',
    },
    {
      label: 'restart',
      action: 'restart',
      disabled: (status: 'resting' | 'running') => status === 'resting',
      status: 'warning' as const,
      icon: 'icon-refresh',
    },
    {
      label: 'shutdown',
      action: 'shutdown',
      disabled: () => false,
      status: 'danger' as const,
      icon: 'icon-poweroff',
    },
  ];

  const dataReloadButtons = [
    { label: 'dataReloadEvents', action: 'reloadEvents', icon: 'icon-compass' },
    {
      label: 'dataReloadMaps',
      action: 'reloadMaps',
      icon: 'icon-mind-mapping',
    },
    {
      label: 'dataReloadPortals',
      action: 'reloadPortals',
      icon: 'icon-common',
    },
  ];

  const loadSeverStatus = async () => {
    setLoading(true);
    try {
      const { data } = await getServerStatus();
      serverStatus.value = data ? 'running' : 'resting';
    } finally {
      setLoading(false);
    }
  };

  onMounted(() => {
    loadSeverStatus();
  });

  const handleButtonClick = async (action: string) => {
    if (action === 'shutdown') {
      shutdownConfirmVisible.value = true;
      return;
    }
    if (action === 'restart') {
      restartConfirmVisible.value = true;
      return;
    }

    setLoading(true);
    try {
      switch (action) {
        case 'start':
          await startServer();
          break;
        case 'stop':
          stopConfigVisible.value = true;
          setLoading(false);
          return;
        case 'restart':
          await restartServer();
          break;
        case 'reloadEvents':
          await reloadEventsByGMCommand();
          break;
        case 'reloadMaps':
          await reloadMapsByGMCommand();
          break;
        case 'reloadPortals':
          await reloadPortalsByGMCommand();
          break;
        default:
          break;
      }

      Message.success(t('common.operationSuccess'));
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      await loadSeverStatus();
      setLoading(false);
    }
  };

  const handleShutdownConfirm = async () => {
    try {
      setLoading(true);
      await shutdown();
      Message.success(t('workplace.button.shutdown.success'));
      // 立即尝试更新服务器状态
      await loadSeverStatus();
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      shutdownConfirmVisible.value = false;
      setLoading(false);
    }
  };

  const handleShutdownCancel = () => {
    shutdownConfirmVisible.value = false;
  };

  const handleRestartConfirm = async () => {
    try {
      setLoading(true);
      await restartServer();
      Message.success(t('common.operationSuccess'));
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      restartConfirmVisible.value = false;
      setLoading(false);
    }
  };

  const handleRestartCancel = () => {
    restartConfirmVisible.value = false;
  };
  const handleStopConfigOk = async () => {
    try {
      setLoading(true);
      const stopConfigParams = {
        minutes: stopConfigData.minutes,
        shutdownMsg: stopConfigData.shutdownMsg,
        showServerMsg: stopConfigData.showServerMsg,
        showCenterMsg: stopConfigData.showCenterMsg,
        showChatMsg: stopConfigData.showChatMsg,
      };

      await stopServer(stopConfigParams);
      Message.success(t('workplace.stop.shutdownInProgress'));

      // 如果设置了延迟时间，则启动一个定时器，在延迟时间结束后更新服务器状态
      if (stopConfigData.minutes > 0) {
        setTimeout(async () => {
          await loadSeverStatus();
        }, stopConfigData.minutes * 60 * 1000);
      } else {
        // 如果没有设置延迟时间，立即更新服务器状态
        await loadSeverStatus();
      }

      stopConfigVisible.value = false;
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleStopConfigCancel = () => {
    Object.assign(stopConfigData, {
      minutes: 0,
      shutdownMsg: '',
      showServerMsg: false,
      showCenterMsg: false,
      showChatMsg: false,
    });
    stopConfigVisible.value = false;
  };

  const handleBroadcastOk = async () => {
    if (!broadcastData.message.trim()) {
      Message.warning(t('workplace.broadcast.message.required'));
      return false;
    }
    try {
      setLoading(true);
      await sendServerBroadcast({ message: broadcastData.message.trim() });
      Message.success(t('common.operationSuccess'));
      handleBroadcastCancel();
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
    return true;
  };

  const handleBroadcastCancel = () => {
    broadcastData.message = '';
    broadcastVisible.value = false;
  };

  const handleSiegeOk = async () => {
    const monsterIds = parseMonsterIds(siegeData.monsterIds);
    if (!monsterIds.length) {
      Message.warning(t('workplace.siege.monsterIds.required'));
      return false;
    }
    try {
      setLoading(true);
      const { data } = await startMonsterSiege({
        monsterIds,
        count: siegeData.count,
        message: siegeData.message.trim(),
        broadcast: siegeData.broadcast,
      });
      Message.success(t('workplace.siege.success', { count: data }));
      handleSiegeCancel();
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
    return true;
  };

  const handleClearSiege = async () => {
    try {
      setLoading(true);
      const { data } = await clearMonsterSiege();
      Message.success(t('workplace.siege.clearSuccess', { count: data }));
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleSiegeCancel = () => {
    Object.assign(siegeData, {
      monsterIds: '',
      count: 1,
      broadcast: true,
      message: '怪物攻城开始！请前往自由市场入口迎战！',
    });
    siegeVisible.value = false;
  };

  const parseMonsterIds = (value: string) => {
    return value
      .split(/[\s,，;；]+/)
      .map((id) => Number(id.trim()))
      .filter((id) => Number.isInteger(id) && id > 0);
  };

  const appendBossId = (id: number) => {
    const monsterIds = parseMonsterIds(siegeData.monsterIds);
    if (!monsterIds.includes(id)) {
      monsterIds.push(id);
    }
    siegeData.monsterIds = monsterIds.join(', ');
  };
</script>

<script lang="ts">
  export default {
    name: 'Dashboard',
  };
</script>

<style lang="less" scoped>
  .button-group {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }
</style>
