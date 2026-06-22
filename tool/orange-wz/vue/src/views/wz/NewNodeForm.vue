<template>
  <el-dialog v-model="visible" title="创建子节点" width="500">
    <el-form :label-width="60" @submit.prevent="saveNodeClick">
      <el-form-item label="父节点">
        {{ nodeParentName }}
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="formData.name" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="formData.type">
          <el-option
            v-for="item in nodeTypeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item v-show="isNormalValue(formData.type)" label="值">
        <el-input v-model="formData.value" />
      </el-form-item>
      <el-form-item v-show="formData.type == 'IMAGE_VECTOR'" label="X">
        <el-input v-model="formData.x" />
      </el-form-item>
      <el-form-item v-show="formData.type == 'IMAGE_VECTOR'" label="Y">
        <el-input v-model="formData.y" />
      </el-form-item>
      <el-form-item v-show="formData.type == 'IMAGE_CANVAS'" label="图片">
        <el-upload
          :on-change="pngSelected"
          accept=".png"
          :auto-upload="false"
          :show-file-list="false"
        >
          <el-button type="primary">选择图片</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item label="压缩" v-show="formData.type == 'IMAGE_CANVAS'">
        <el-select v-model="formData.pngFormat">
          <el-option
            v-for="item in formatOptions"
            :key="item.id"
            :label="item.value"
            :value="item.value"
            :disabled="item.disabled"
          >
            <span style="float: left">{{ item.value }}</span>
            <span style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
              {{ item.label }}
            </span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item v-if="formData.type == 'IMAGE_CANVAS' && formData.png" label="预览">
        <el-image :src="'data:image/png;base64,' + formData.png" />
      </el-form-item>
      <el-form-item v-show="formData.type == 'IMAGE_SOUND'" label="音频">
        <el-upload
          v-show="formData.type == 'IMAGE_SOUND'"
          :on-change="mp3Selected"
          accept=".mp3"
          :auto-upload="false"
          :show-file-list="false"
        >
          <el-button type="primary">选择音频</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item label="预览" v-if="formData.type == 'IMAGE_SOUND' && formData.mp3">
        <audio controls :key="formData.mp3" loop>
          <source :src="'data:audio/wav;base64,' + formData.mp3" />
        </audio>
      </el-form-item>
      <el-form-item>
        <el-button type="success" native-type="submit">保存</el-button>
      </el-form-item>
    </el-form>
  </el-dialog>
</template>

<script setup lang="ts">
  import { addNode } from '@/api/wz.ts';
  import {
    getDefaultWzNodeValue,
    getFormatOptions,
    type IWzNode,
    type IWzNodeValue,
  } from '@/store/wzEditor.ts';
  import { isNormalValue } from '@/utils/wzUtils.ts';
  import { ref } from 'vue';

  const pFunc = defineEmits(['insertNode']);

  const visible = ref<boolean>(false);
  const nodeParentName = ref<string>('');
  const formData = ref<IWzNodeValue>(getDefaultWzNodeValue());
  const formatOptions = ref(getFormatOptions());
  const nodeTypeOptions = ref<{ label: string; value: string }[]>([]);
  const currentNode = ref<IWzNode>();
  const pId = ref<number>(-1);

  const initial = (data: IWzNode) => {
    nodeParentName.value = data.name;
    pId.value = data.id;

    formData.value.id = data.id;
    formData.value.name = undefined;
    formData.value.value = undefined;
    formData.value.x = undefined;
    formData.value.y = undefined;
    formData.value.png = undefined;
    formData.value.mp3 = undefined;
    if (data.type == 'WZ' || data.type == 'WZ_DIRECTORY') {
      formData.value.type = 'IMAGE';
      nodeTypeOptions.value = [
        { label: '文件夹', value: 'WZ_DIRECTORY' },
        { label: 'IMG', value: 'IMAGE' },
      ];
    } else if (
      data.type == 'IMAGE' ||
      data.type == 'IMAGE_LIST' ||
      data.type == 'IMAGE_CANVAS' ||
      data.type == 'IMAGE_CONVEX'
    ) {
      formData.value.type = 'IMAGE_LIST';
      nodeTypeOptions.value = [
        { label: 'list', value: 'IMAGE_LIST' },
        { label: 'string', value: 'IMAGE_STRING' },
        { label: 'short', value: 'IMAGE_SHORT' },
        { label: 'int', value: 'IMAGE_INT' },
        { label: 'long', value: 'IMAGE_LONG' },
        { label: 'float', value: 'IMAGE_FLOAT' },
        { label: 'double', value: 'IMAGE_DOUBLE' },
        { label: 'canvas', value: 'IMAGE_CANVAS' },
        { label: 'convex', value: 'IMAGE_CONVEX' },
        { label: 'vector', value: 'IMAGE_VECTOR' },
        { label: 'uol', value: 'IMAGE_UOL' },
        { label: 'sound', value: 'IMAGE_SOUND' },
        { label: 'null', value: 'IMAGE_NULL' },
      ];
    } else {
      ElMessage.error({
        message: '该分类不能添加子类',
      });
      return;
    }

    currentNode.value = data;
    visible.value = true;
  };

  const pngSelected = async (uploadFile: UploadFile) => {
    try {
      const base64 = await convertToBase64(uploadFile.raw);
      const pureBase64 = base64.split(',')[1];
      formData.value.png = pureBase64;

      return pureBase64;
    } catch (error) {
      ElMessage.error({
        message: `图片识别失败:${error}`,
        duration: 3000,
      });
    }
  };

  const convertToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = (error) => reject(error);
      reader.readAsDataURL(file);
    });
  };

  const saveNodeClick = async () => {
    // 创建子节点
    const { data } = await addNode(formData.value);
    pFunc('insertNode', pId.value, data);
    visible.value = false;
    ElMessage.success({
      message: '操作成功',
    });
  };

  const mp3Selected = async (uploadFile: UploadFile) => {
    try {
      const base64 = await convertToBase64(uploadFile.raw);
      const pureBase64 = base64.split(',')[1];
      formData.value.mp3 = pureBase64;

      return pureBase64;
    } catch (error) {
      ElMessage.error({
        message: `音频识别失败:${error}`,
        duration: 3000,
      });
    }
  };

  defineExpose({ initial });
</script>

<style scoped></style>
