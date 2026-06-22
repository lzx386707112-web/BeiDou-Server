<template>
  <el-card>
    <template #header>
      <span>Wz 编辑器</span>
    </template>
    <el-button type="primary" :icon="AiOutlineFolderOpen" @click="loadClick">打开</el-button>
    <el-button type="primary" :icon="AiOutlinePlus" @click="addViewClick">视图</el-button>
    <el-button
      :type="synView ? 'success' : 'info'"
      :icon="AiOutlineSync"
      @click="synView = !synView"
    >
      同步
    </el-button>
    <el-button type="primary" :icon="AiOutlineFolderOpen" @click="expandClick">展开</el-button>
    <el-popconfirm
      placement="top"
      :width="250"
      :icon="BsRecycle"
      icon-color="orange"
      title="回收内存，释放文件占用。如果文件已关闭，还提示被占用的话，使用该功能可以解除占用。"
      confirm-button-text="是"
      @confirm="gcClick"
      confirm-button-type="warning"
      cancel-button-text="否"
    >
      <template #reference>
        <el-button type="warning" :icon="BsRecycle">内存</el-button>
      </template>
    </el-popconfirm>
    <el-popconfirm
      placement="top"
      :width="250"
      :icon="BsTrash"
      icon-color="red"
      title="关闭所有打开的文件，重置缓存，并回收内存，是否继续？"
      confirm-button-text="是"
      @confirm="deleteCacheClick"
      confirm-button-type="danger"
      cancel-button-text="否"
    >
      <template #reference>
        <el-button type="danger" :icon="BsTrash">缓存</el-button>
      </template>
    </el-popconfirm>
    <el-splitter style="margin-top: 10px">
      <el-splitter-panel v-for="item in viewList" :key="item.id">
        <WzView
          :ref="(el) => setWorkplaceRef(el, item.id)"
          @getViewsId="getViewsId"
          @reInitial="reInitial"
          @syncExpand="syncExpand"
          @syncCollapse="syncCollapse"
          @syncLoadEditForm="syncLoadEditForm"
          @removeView="removeView"
          @setCmsId="setCmsId"
          @chineseClick="chineseClick"
        />
      </el-splitter-panel>
    </el-splitter>
  </el-card>
  <WzLoad ref="WzLoadRef" @loadConfirm="loadConfirm" />
</template>

<script setup lang="ts">
  import { addView, deleteCache, gc, getViews, load, localization } from '@/api/wz.ts';
  import type { IWorkplace } from '@/store/wzEditor.ts';
  import { removeNodeById } from '@/utils/nodeUtils.ts';
  import WzLoad from '@/views/wz/WzLoad.vue';
  import WzView from '@/views/wz/WzView.vue';
  import { ref, useTemplateRef } from 'vue';
  import { AiOutlineFolderOpen, AiOutlinePlus, AiOutlineSync } from 'vue-icons-plus/ai';
  import { BsRecycle, BsTrash } from 'vue-icons-plus/bs';

  /* 视图 -----------------------------------------------------------------------------------------*/
  const viewList = ref<IWorkplace[]>([]);
  const synView = ref<boolean>(true);

  const setWorkplaceRef = (el: typeof WzView | null, id: number) => {
    if (el) {
      const view = viewList.value.find((item) => item.id === id);
      if (view && !view.ref) {
        view.ref = el;
        el.initial(view.id);
      }
    }
  };

  const loadViews = async () => {
    const { data } = await getViews();
    for (const item of data) {
      viewList.value.push({ id: item, ref: null });
    }
  };
  loadViews();

  const addViewClick = async () => {
    const { data } = await addView();
    viewList.value.push({ id: data, ref: null });
  };

  const removeView = (id: number) => {
    removeNodeById(viewList.value, id);
  };

  const getViewsId = (id: number, callback) => {
    const views = [];
    viewList.value.forEach((item) => {
      if (item.id != id) views.push(item.id);
    });
    callback(views);
  };

  const reInitial = (viewId: number) => {
    viewList.value.forEach((item) => {
      if (item.id == viewId) item.ref.initial(viewId);
    });
  };

  const syncExpand = (id: number, path: string) => {
    if (!synView.value) return;
    viewList.value.forEach((item) => {
      if (item.id == id) return;
      item.ref.expandTreeByPath(path);
    });
  };

  const syncCollapse = (id: number, path: string) => {
    if (!synView.value) return;
    viewList.value.forEach((item) => {
      if (item.id == id) return;
      item.ref.collapseTreeByPath(path);
    });
  };

  const syncLoadEditForm = (id: number, path: string) => {
    if (!synView.value) return;
    viewList.value.forEach((item) => {
      if (item.id == id) return;
      item.ref.loadEditFormByPath(path);
    });
  };

  /* 打开 -------------------------------------------------------------------------------------------------------------*/
  const wzLoad = useTemplateRef<WzLoad>('WzLoadRef');
  const loadClick = () => {
    wzLoad.value.initial();
  };

  const loadConfirm = async (id: number, version: number, key: string) => {
    const firstView = viewList.value[0];
    await load(id, firstView.id, version, key);
    await firstView.ref.initial(firstView.id);
  };

  /* 展开 -------------------------------------------------------------------------------------------------------------*/
  const expandClick = () => {
    ElMessageBox.prompt('请粘贴要展开的路径', '路径', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '至少一个字符',
    })
      .then(({ value }) => {
        syncExpand(-520, value);
        ElMessage({
          type: 'success',
          message: `展开路径: ${value}`,
        });
      })
      .catch(() => {
        ElMessage({
          type: 'info',
          message: '操作已取消',
        });
      });
  };

  /* 展开 -------------------------------------------------------------------------------------------------------------*/
  const deleteCacheClick = async () => {
    const { data } = await deleteCache();
    ElMessage.success({
      message: data,
    });
    location.reload();
  };

  const gcClick = async () => {
    const { data } = await gc();
    ElMessage.success({
      message: data,
    });
  };

  /* 汉化 -------------------------------------------------------------------------------------------------------------*/
  const cmsId = ref<number>(-1);
  const setCmsId = (id: number) => {
    cmsId.value = id;
    ElMessage.success({ message: '设置成功，页面刷新前有效。' });
  };

  const chineseClick = async (to: number) => {
    const from = cmsId.value;
    if (!from || from < 0) {
      ElMessage.error({ message: '请先设置汉化用的 WZ' });
      return;
    }
    await localization(from, to);
    ElMessage.success({ message: '操作成功，请手动检查并保存汉化后的 wz' });
  };
</script>

<style scoped></style>
