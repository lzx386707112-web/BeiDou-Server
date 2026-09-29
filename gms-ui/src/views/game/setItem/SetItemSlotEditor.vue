<template>
  <div class="section-heading">
    <span>{{ $t('setItem.create.slots') }}</span>
    <a-button size="small" :disabled="modelValue.length >= 8" @click="addSlot">
      <template #icon><icon-plus /></template>
      {{ $t('setItem.action.addSlot') }}
    </a-button>
  </div>
  <div v-for="(slot, index) in modelValue" :key="index" class="slot-row">
    <div class="slot-header">
      <span>{{ $t('setItem.slot', { index: index + 1 }) }}</span>
      <a-tooltip :content="$t('setItem.action.removeSlot')">
        <a-button
          type="text"
          status="danger"
          size="mini"
          :disabled="modelValue.length <= minimumSlots"
          @click="removeSlot(index)"
        >
          <template #icon><icon-delete /></template>
        </a-button>
      </a-tooltip>
    </div>
    <div class="selected-equipment">
      <div v-for="item in slot" :key="item.id" class="equipment-item">
        <EquipmentIcon compact :item-id="item.id" :alt="item.name" />
        <span class="equipment-text"
          ><strong>{{ item.name }}</strong
          ><small>{{ item.id }}</small></span
        >
        <a-tooltip :content="$t('setItem.action.removeEquipment')">
          <a-button
            type="text"
            status="danger"
            size="mini"
            @click="removeEquipment(index, item.id)"
          >
            <template #icon><icon-close /></template>
          </a-button>
        </a-tooltip>
      </div>
      <a-button
        type="outline"
        size="small"
        :disabled="slot.length >= 10"
        @click="openSearch(index)"
      >
        <template #icon><icon-search /></template
        >{{ $t('setItem.action.addEquipment') }}
      </a-button>
    </div>
  </div>
  <a-modal
    v-model:visible="searchVisible"
    :width="'min(720px, calc(100vw - 32px))'"
    :title="$t('setItem.equipmentSearch.title')"
    :footer="false"
    unmount-on-close
  >
    <a-space class="search-toolbar">
      <a-input
        v-model="keyword"
        allow-clear
        :placeholder="$t('setItem.equipmentSearch.placeholder')"
        @press-enter="search(1)"
        ><template #prefix><icon-search /></template
      ></a-input>
      <a-button type="primary" :loading="searching" @click="search(1)">
        <template #icon><icon-search /></template
        >{{ $t('setItem.action.search') }}
      </a-button>
    </a-space>
    <a-table
      row-key="id"
      :data="results"
      :loading="searching"
      :scroll="{ x: appStore.device === 'mobile' ? undefined : 520, y: 380 }"
      :pagination="{ current: page, pageSize: 30, total, showTotal: true }"
      @page-change="search"
    >
      <template #columns>
        <a-table-column
          :title="$t('setItem.column.preview')"
          :width="76"
          align="center"
        >
          <template #cell="{ record }">
            <a-popover
              :position="appStore.device === 'mobile' ? 'bottom' : 'right'"
              trigger="hover"
              auto-fit-position
              :content-style="{ padding: 0, background: 'transparent' }"
            >
              <EquipmentIcon compact :item-id="record.id" :alt="record.name" />
              <template #content>
                <EquipmentTooltip
                  :item="record"
                  :style="{ width: 'min(326px, calc(100vw - 32px))' }"
                />
              </template>
            </a-popover>
          </template>
        </a-table-column>
        <a-table-column
          v-if="appStore.device !== 'mobile'"
          :title="$t('setItem.column.itemId')"
          data-index="id"
          :width="110"
        />
        <a-table-column
          :title="$t('setItem.column.itemName')"
          data-index="name"
          :width="appStore.device === 'mobile' ? undefined : 244"
        >
          <template #cell="{ record }">
            <span>{{ record.name }}</span>
            <small v-if="appStore.device === 'mobile'" class="search-item-id">{{
              record.id
            }}</small>
          </template>
        </a-table-column>
        <a-table-column
          :title="$t('setItem.column.operation')"
          :width="90"
          align="center"
          fixed="right"
        >
          <template #cell="{ record }">
            <a-button
              type="text"
              size="small"
              :disabled="selectedIds.has(record.id)"
              @click="select(record)"
            >
              <template #icon><icon-plus /></template
              >{{ $t('setItem.action.select') }}
            </a-button>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useAppStore } from '@/store';
  import { SetItemEquipment } from '@/api/setItem';
  import {
    EquipmentCatalogItem,
    getEquipmentCatalog,
  } from '@/api/equipmentCatalog';
  import EquipmentIcon from '@/views/game/equipmentCatalog/EquipmentIcon.vue';
  import EquipmentTooltip from '@/views/game/equipmentCatalog/EquipmentTooltip.vue';

  const props = withDefaults(
    defineProps<{
      modelValue: SetItemEquipment[][];
      minimumSlots?: number;
    }>(),
    { minimumSlots: 1 }
  );
  const emit = defineEmits<{
    (event: 'update:modelValue', slots: SetItemEquipment[][]): void;
  }>();
  const appStore = useAppStore();
  const searchVisible = ref(false);
  const searching = ref(false);
  const keyword = ref('');
  const submittedKeyword = ref('');
  const results = ref<EquipmentCatalogItem[]>([]);
  const page = ref(1);
  const total = ref(0);
  const targetSlot = ref(0);
  let searchVersion = 0;
  const selectedIds = computed(
    () => new Set(props.modelValue.flat().map((item) => item.id))
  );
  const addSlot = () => emit('update:modelValue', [...props.modelValue, []]);
  const removeSlot = (index: number) =>
    emit(
      'update:modelValue',
      props.modelValue.filter((_, i) => i !== index)
    );
  const removeEquipment = (index: number, id: number) =>
    emit(
      'update:modelValue',
      props.modelValue.map((slot, i) =>
        i === index ? slot.filter((item) => item.id !== id) : slot
      )
    );
  const openSearch = (index: number) => {
    searchVersion += 1;
    searching.value = false;
    targetSlot.value = index;
    keyword.value = '';
    results.value = [];
    total.value = 0;
    page.value = 1;
    searchVisible.value = true;
  };
  const search = async (nextPage: number) => {
    if (nextPage === 1) submittedKeyword.value = keyword.value.trim();
    if (!submittedKeyword.value) return;
    searchVersion += 1;
    const version = searchVersion;
    searching.value = true;
    try {
      const { data } = await getEquipmentCatalog({
        keyword: submittedKeyword.value,
        pageNo: nextPage,
        pageSize: 30,
      });
      if (version !== searchVersion) return;
      results.value = data.records;
      total.value = data.total;
      page.value = data.pageNo;
    } finally {
      if (version === searchVersion) searching.value = false;
    }
  };
  const select = (item: EquipmentCatalogItem) => {
    if (
      selectedIds.value.has(item.id) ||
      !props.modelValue[targetSlot.value] ||
      props.modelValue[targetSlot.value].length >= 10
    )
      return;
    emit(
      'update:modelValue',
      props.modelValue.map((slot, i) =>
        i === targetSlot.value ? [...slot, item] : slot
      )
    );
    searchVisible.value = false;
  };
</script>

<style scoped lang="less">
  .section-heading,
  .slot-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .section-heading {
    margin-bottom: 10px;
    font-weight: 600;
  }
  .slot-row {
    padding: 12px 0;
    border-top: 1px solid var(--color-border-2);
  }
  .slot-header {
    margin-bottom: 8px;
    color: var(--color-text-2);
  }
  .selected-equipment {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .equipment-item {
    display: flex;
    max-width: 100%;
    width: 260px;
    align-items: center;
    gap: 8px;
    padding: 4px;
    border: 1px solid var(--color-border-2);
    border-radius: 4px;
  }
  .equipment-text {
    flex: 1;
    min-width: 0;
    strong,
    small {
      display: block;
      overflow-wrap: anywhere;
    }
    small {
      color: var(--color-text-3);
    }
  }
  .search-toolbar {
    display: flex;
    margin-bottom: 16px;
  }
  .search-item-id {
    display: block;
    color: var(--color-text-3);
  }
</style>
