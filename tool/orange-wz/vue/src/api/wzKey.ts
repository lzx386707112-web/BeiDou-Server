import { api } from '@/api/interceptor.ts';

const apiPath = '/admin/wzKey';

export interface WzKeyDto {
  id: number;
  name: string;
  iv: string[] | string;
  userKey: string[] | string;
}

export function getWzKeys() {
  return api.get(`${apiPath}`);
}

export function saveWzKey(data: WzKeyDto) {
  return api.post(`${apiPath}`, data);
}

export function updateWzKey(data: WzKeyDto) {
  return api.post(`${apiPath}/${data.id}`, data);
}

export function deleteWzKey(id: number) {
  return api.delete(`${apiPath}/${id}`);
}
