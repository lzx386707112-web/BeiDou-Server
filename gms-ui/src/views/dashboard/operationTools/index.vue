<template>
  <div class="container">
    <Breadcrumb />
    <a-card class="general-card" :title="$t('workplace.operationTools')">
      <a-space direction="vertical" fill :size="16">
        <a-card :title="$t('workplace.button.broadcast')" :bordered="false">
          <a-form :model="broadcastData" layout="vertical">
            <a-form-item :label="$t('workplace.broadcast.message')">
              <a-textarea
                v-model="broadcastData.message"
                :max-length="100"
                show-word-limit
              />
            </a-form-item>
            <a-button type="primary" :loading="loading" @click="handleBroadcast">
              <template #icon>
                <icon-notification />
              </template>
              {{ $t('workplace.button.broadcast') }}
            </a-button>
          </a-form>
        </a-card>

        <a-card :title="$t('workplace.button.monsterSiege')" :bordered="false">
          <a-form :model="siegeData" layout="vertical">
            <a-form-item :label="$t('workplace.siege.map')">
              <a-select v-model="siegeData.mapId">
                <a-option v-for="map in siegeMapOptions" :key="map.id" :value="map.id">
                  {{ map.name }}（{{ map.id }}）
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item :label="$t('workplace.siege.customMapId')">
              <a-input-number
                v-model="siegeData.customMapId"
                :min="1"
                :placeholder="$t('workplace.siege.customMapId.placeholder')"
              />
            </a-form-item>
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
            <a-form-item :label="$t('workplace.siege.rewards')">
              <a-space direction="vertical" fill>
                <a-space v-for="reward in siegeData.rewards" :key="reward.rank">
                  <span>{{ $t('workplace.siege.rankReward', { rank: reward.rank }) }}</span>
                  <a-input-number v-model="reward.itemId" :min="0" :placeholder="$t('workplace.siege.rewardItemId')" />
                  <a-input-number v-model="reward.quantity" :min="1" :max="32767" :placeholder="$t('workplace.siege.rewardQuantity')" />
                </a-space>
              </a-space>
            </a-form-item>
            <a-space>
              <a-button
                type="primary"
                status="warning"
                :loading="loading"
                @click="handleSiege"
              >
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
        </a-card>
      </a-space>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { reactive } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { useI18n } from 'vue-i18n';
  import useLoading from '@/hooks/loading';
  import { shenshuoSiegeBossOptions, siegeMapOptions } from '../siege-maps';
  import {
    clearMonsterSiege,
    sendServerBroadcast,
    startMonsterSiege,
  } from '@/api/dashboard';

  const { t } = useI18n();
  const { loading, setLoading } = useLoading(false);
  const broadcastData = reactive({
    message: '',
  });
  const siegeData = reactive({
    mapId: 910000000,
    customMapId: undefined as number | undefined,
    monsterIds: '',
    count: 1,
    broadcast: true,
    message: '怪物攻城开始！请前往指定主城迎战！',
    rewards: [1, 2, 3].map((rank) => ({ rank, itemId: 0, quantity: 1 })),
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
    { name: '麦格纳斯', id: 8880000 },
    { name: '露希妲', id: 8880140 },
    { name: '威尔', id: 8880300 },
    { name: '塞伦', id: 8880340 },
    { name: '黑魔法师', id: 8880502 },
    { name: '戴斯克', id: 8644630 },
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
    ...shenshuoSiegeBossOptions,
  ];

  const handleBroadcast = async () => {
    if (!broadcastData.message.trim()) {
      Message.warning(t('workplace.broadcast.message.required'));
      return;
    }
    try {
      setLoading(true);
      await sendServerBroadcast({ message: broadcastData.message.trim() });
      Message.success(t('common.operationSuccess'));
      broadcastData.message = '';
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleSiege = async () => {
    const monsterIds = parseMonsterIds(siegeData.monsterIds);
    if (!monsterIds.length) {
      Message.warning(t('workplace.siege.monsterIds.required'));
      return;
    }
    try {
      setLoading(true);
      const { data } = await startMonsterSiege({
        mapId: getSiegeMapId(),
        monsterIds,
        count: siegeData.count,
        message: siegeData.message.trim(),
        broadcast: siegeData.broadcast,
        rewards: siegeData.rewards.filter((reward) => reward.itemId > 0),
      });
      Message.success(t('workplace.siege.success', { count: data }));
      Object.assign(siegeData, {
        monsterIds: '',
        count: 1,
        broadcast: true,
        message: '怪物攻城开始！请前往指定主城迎战！',
      });
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleClearSiege = async () => {
    try {
      setLoading(true);
      const { data } = await clearMonsterSiege(getSiegeMapId());
      Message.success(t('workplace.siege.clearSuccess', { count: data }));
    } catch (err) {
      console.error(err);
      Message.error(t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  };

  const parseMonsterIds = (value: string) => {
    return value
      .split(/[\s,，;；]+/)
      .map((id) => Number(id.trim()))
      .filter((id) => Number.isInteger(id) && id > 0);
  };

  const getSiegeMapId = () => siegeData.customMapId || siegeData.mapId;

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
    name: 'OperationTools',
  };
</script>
