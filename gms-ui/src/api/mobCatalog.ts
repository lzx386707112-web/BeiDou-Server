import axios from 'axios';

export interface MobCatalogItem {
  id: number;
  name: string;
  stats: Record<string, number>;
  iconAvailable: boolean;
}

export interface MobCatalogPage {
  records: MobCatalogItem[];
  pageNo: number;
  pageSize: number;
  total: number;
}

export interface MobCatalogParams {
  keyword?: string;
  pageNo?: number;
  pageSize?: number;
  minLevel?: number;
  maxLevel?: number;
}

export interface MobDropItem {
  id: number;
  dropperId: number;
  dropperName: string;
  itemId: number;
  itemName: string;
  itemCategory: string;  // 物品类别：装备、消耗、设置、其他、特殊、金币
  minimumQuantity: number;
  maximumQuantity: number;
  questId: number;
  questName: string;
  chance: number;
  comments: string;
}

export interface AddDropParams {
  itemId: number;
  minimumQuantity: number;
  maximumQuantity: number;
  chance: number;
  questId?: number;
  comments?: string;
}

export function getMobCatalog(params: MobCatalogParams) {
  return axios.get<MobCatalogPage>('/mob/v1/catalog', { params });
}

export function getMobDrops(mobId: number) {
  return axios.get<MobDropItem[]>(`/mob/v1/${mobId}/drops`);
}

export function addMobDrop(mobId: number, data: AddDropParams) {
  return axios.put(`/mob/v1/${mobId}/drops`, { data });
}

export function deleteMobDrop(dropId: number) {
  return axios.delete(`/mob/v1/drops/${dropId}`);
}

/**
 * 获取怪物图标URL
 */
export function getMobPreviewUrl(id: string | number): string {
  if (!id || Number(id) <= 0) return '';
  const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
  return `${apiBase}/assets/mob-icons/${id}.png`;
}

/**
 * 怪物图标加载失败时的 fallback
 */
export function handleMobPreviewError(event: Event, id: number) {
  const img = event.target as HTMLImageElement;
  if (!img) return;

  // 使用 dataset 跟踪 fallback 状态
  if (!img.dataset.previewFallback) {
    img.dataset.previewFallback = 'failed';
    // 可以尝试其他来源，目前直接隐藏
    img.style.visibility = 'hidden';
  }
}
