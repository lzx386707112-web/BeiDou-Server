<template>
  <div class="dropdown-container">
    <el-dropdown
      ref="dropdownRef"
      virtual-triggering
      :virtual-ref="triggerRef"
      :show-arrow="false"
      :popper-options="{
        modifiers: [{ name: 'offset', options: { offset: [0, 0] } }],
      }"
      trigger="contextmenu"
      placement="bottom-start"
      @command="handleCommand"
    >
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item disabled>{{ menuName }}</el-dropdown-item>
          <template v-for="(item, index) in menuItems" :key="index">
            <template v-if="item.children && item.children.length > 0">
              <el-dropdown-item disabled :divided="item.divided">
                <el-dropdown
                  placement="bottom-start"
                  style="height: 22px; line-height: 22px"
                  :show-arrow="false"
                  @command="handleCommand"
                  :popper-options="{
                    modifiers: [{ name: 'offset', options: { offset: [110, -22] } }],
                  }"
                >
                  <span class="export-dropdown-trigger">
                    <span>{{ item.name }}</span>
                    <span class="dropdown-arrow">▶</span>
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <template v-for="(subItem, subIndex) in item.children" :key="subIndex">
                        <el-dropdown-item :command="subItem.command" :divided="subItem.divided">
                          {{ subItem.name }}
                        </el-dropdown-item>
                      </template>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </el-dropdown-item>
            </template>
            <template v-else>
              <el-dropdown-item :command="item.command" :divided="item.divided">
                {{ item.name }}
              </el-dropdown-item>
            </template>
          </template>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
  import { ref, useTemplateRef } from 'vue';

  const pFunc = defineEmits(['handleContextMenu']);

  const dropdownRef = useTemplateRef<DropdownInstance>('dropdownRef');
  const position = ref({
    top: 0,
    left: 0,
    bottom: 0,
    right: 0,
  } as DOMRect);

  const triggerRef = ref({
    getBoundingClientRect: () => position.value,
  });

  const menuName = ref<string>('');
  const menuItems = ref([]);

  const openMenu = (name: string, items: [], x: number, y: number) => {
    menuName.value = name;
    menuItems.value = items;
    position.value = DOMRect.fromRect({
      x: x,
      y: y,
    });
    dropdownRef.value.handleOpen();
  };
  defineExpose({ openMenu });

  const handleCommand = (action: string) => {
    pFunc('handleContextMenu', action);
  };
</script>

<style scoped>
  .dropdown-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 0;
    height: 0;
    overflow: hidden;
    pointer-events: none;
  }

  .dropdown-container :deep(.el-dropdown) {
    position: absolute;
  }

  .export-dropdown-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 110px; /* 根据需要调整 */
  }

  .dropdown-arrow {
    margin-left: 8px; /* 调整箭头与文字的间距 */
    font-size: 12px;
  }
</style>
