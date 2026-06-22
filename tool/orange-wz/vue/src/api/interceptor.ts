import axios from 'axios';
import { ElLoading, ElMessage } from 'element-plus';
const baseUrl = import.meta.env.VITE_API_BASE_URL;
let loadingInstance: LoadingInstance;

export const api = axios.create({
  timeout: 600000, // 10分钟
  baseURL: baseUrl,
  headers: {
    'Content-Type': 'application/json;charset=UTF-8',
  },
});

api.interceptors.request.use((config) => {
  loadingInstance = ElLoading.service({
    lock: true,
    text: 'loading...',
  });
  return config;
});

api.interceptors.response.use(
  (response) => {
    loadingInstance.close();
    if (response.data.code != 20000) {
      ElMessage({
        message: response.data.message,
        type: 'error',
        duration: 3 * 1000,
      });
      return Promise.reject();
    }
    return response.data;
  },
  (error) => {
    const msg = error.message !== undefined ? error.message : '';
    ElMessage({
      message: `网络错误 ${msg}`,
      type: 'error',
      duration: 3 * 1000,
    });
    loadingInstance.close();
    return Promise.reject(error);
  },
);
