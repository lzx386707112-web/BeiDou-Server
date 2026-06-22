<template>
  <el-dialog v-model="visible" title="选择密钥" width="500">
    <el-form ref="keyRef" label-width="60">
      <el-form-item label="版本">
        <el-input
          v-model="formData.version"
          @input="handleVersionInput"
          @change="handleVersionChange"
        />
      </el-form-item>
      <el-form-item label="密钥">
        <el-select v-model="formData.key" @change="keySelected" :disabled="editMode">
          <el-option v-for="item in wzKeys" :key="item.id" :label="item.name" :value="item.name">
            <span style="float: left">{{ item.name }}</span>
            <span
              v-if="isSystemConf(item.name)"
              style="float: right; color: var(--el-text-color-secondary); font-size: 13px"
            >
              不可修改
            </span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="操作">
        <el-button
          size="small"
          :type="editMode ? 'info' : 'primary'"
          @click="editMode = !editMode"
          :disabled="isSystemConf(formData.key)"
        >
          编辑模式
        </el-button>
        <el-button size="small" type="success" @click="copyClick">复制方案</el-button>
        <el-button
          size="small"
          v-show="!isSystemConf(formData.key)"
          type="danger"
          @click="deleteClick"
        >
          删除方案
        </el-button>
        <el-button
          size="small"
          v-show="editMode && !isSystemConf(formData.key)"
          type="warning"
          @click="updateClick"
        >
          更新方案
        </el-button>
      </el-form-item>
      <el-form-item label="重命名" v-show="editMode">
        <el-input v-model="formData.key" />
      </el-form-item>
      <el-form-item label="IV" v-show="editMode">
        <el-row :gutter="8">
          <template v-for="(item, index) in formData.iv" :key="index">
            <el-col :span="6">
              <el-input
                v-model="formData.iv[index]"
                @input="handleIvInput(index, formData.iv[index])"
                @change="handleIvChange(index, formData.iv[index])"
              />
            </el-col>
          </template>
        </el-row>
      </el-form-item>
      <el-form-item label="Key" v-show="editMode">
        <el-row :gutter="8">
          <template v-for="(item, index) in formData.userKey" :key="index">
            <el-col :span="6" v-if="index % 4 == 0">
              <el-input
                v-model="formData.userKey[index]"
                @input="handleKeyInput(index, formData.userKey[index])"
                @change="handleKeyChange(index, formData.iv[index])"
              />
            </el-col>
          </template>
        </el-row>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="okClick">确定</el-button>
      </el-form-item>
    </el-form>
  </el-dialog>
</template>

<script setup lang="ts">
  import { deleteWzKey, getWzKeys, saveWzKey, updateWzKey, type WzKeyDto } from '@/api/wzKey.ts';
  import { WzKeyHexConverter } from '@/utils/wzKeyHexConverter.ts';
  import { ref } from 'vue';

  const pFunc = defineEmits(['confirmWzKey']);

  const visible = ref<boolean>(false);
  const wzKeys = ref<WzKeyDto[]>([]);
  const editMode = ref<boolean>(false);

  const formData = ref({
    version: '',
    keyId: undefined,
    key: '',
    iv: [],
    userKey: [],
  });

  const loadWzKeys = async () => {
    const { data } = await getWzKeys();
    wzKeys.value = [];
    for (let i = 0; i < data.length; i++) {
      wzKeys.value.push(WzKeyHexConverter.convertToHexArrays(data[i]));
    }
  };

  const initial = async () => {
    visible.value = true;
    formData.value.version = localStorage.getItem('wzVersion') || '95';
    formData.value.key = localStorage.getItem('wzKey') || 'GMS';
    await loadWzKeys();
    keySelected();
  };
  defineExpose({ initial });

  const keySelected = () => {
    const key = wzKeys.value.find((item) => item.name === formData.value.key);
    if (key) {
      formData.value.keyId = key.id;
      formData.value.iv = key.iv;
      formData.value.userKey = key.userKey;
    }
  };

  const copyClick = async () => {
    ElMessageBox.prompt('请输入方案名称', '复制方案', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '至少一个字符',
    })
      .then(async ({ value }) => {
        const wzKey = ref<WzKeyDto>({
          keyId: undefined,
          name: value,
          iv: formData.value.iv,
          userKey: formData.value.userKey,
        });
        const { data } = await saveWzKey(WzKeyHexConverter.convertToBase64(wzKey.value));
        wzKeys.value.push(WzKeyHexConverter.convertToHexArrays(data));
        formData.value.key = data.name;
        formData.value.keyId = data.id;
        keySelected();
        editMode.value = true;
        ElMessage.success({ message: '方案已创建' });
      })
      .catch(() => {
        ElMessage({
          type: 'info',
          message: '操作已取消',
        });
      });
  };

  const deleteClick = async () => {
    await deleteWzKey(formData.value.keyId);
    wzKeys.value = wzKeys.value.filter((item) => item.id !== formData.value.keyId);
    formData.value.key = 'GMS';
    keySelected();
    ElMessage.success({ message: '方案已删除' });
  };

  const updateClick = async () => {
    const wzKey = ref<WzKeyDto>({
      id: formData.value.keyId,
      name: formData.value.key,
      iv: formData.value.iv,
      userKey: formData.value.userKey,
    });
    await updateWzKey(WzKeyHexConverter.convertToBase64(wzKey.value));
    const wzKey2 = wzKeys.value.find((item) => item.id === formData.value.keyId);
    if (wzKey2) {
      wzKey2.name = formData.value.key;
      wzKey2.iv = formData.value.iv;
      wzKey2.userKey = formData.value.userKey;
    }
    ElMessage.success({ message: '方案已更新' });
  };

  const okClick = () => {
    pFunc('confirmWzKey', formData.value.version, formData.value.key);
    localStorage.setItem('wzVersion', formData.value.version);
    localStorage.setItem('wzKey', formData.value.key);
    visible.value = false;
  };

  const isSystemConf = (name: string): boolean => {
    return ['GMS', 'CMS', 'LATEST'].includes(name);
  };

  const handleVersionInput = (value: number) => {
    formData.value.version = value.replace(/[^0-9]/g, '');
  };

  const handleVersionChange = (value: number) => {
    if (value == undefined || value == '' || value == null) {
      formData.value.version = 0;
    }
  };

  const handleIvInput = (index: number, value: string) => {
    let filteredValue = value.replace(/[^a-zA-Z0-9]/g, '');
    filteredValue = filteredValue.toUpperCase();
    if (filteredValue.length > 2) {
      filteredValue = filteredValue.substring(0, 2);
    }

    formData.value.iv[index] = filteredValue;
  };

  const handleIvChange = (index: number, value: string) => {
    if (value == undefined || value == '' || value == null) {
      formData.value.iv[index] = '00';
    }
  };

  const handleKeyInput = (index: number, value: string) => {
    let filteredValue = value.replace(/[^a-zA-Z0-9]/g, '');
    filteredValue = filteredValue.toUpperCase();
    if (filteredValue.length > 2) {
      filteredValue = filteredValue.substring(0, 2);
    }

    formData.value.userKey[index] = filteredValue;
  };

  const handleKeyChange = (index: number, value: string) => {
    if (value == undefined || value == '' || value == null) {
      formData.value.userKey[index] = '00';
    }
  };
</script>

<style scoped></style>
