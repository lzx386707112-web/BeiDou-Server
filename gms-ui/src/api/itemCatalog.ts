import axios from 'axios';

export interface ItemCatalogCategory {
  key: string;
  count: number;
}

export interface ItemCatalogItem {
  id: number;
  name: string;
  description: string;
  category: string;
  specs: Record<string, any>;
  iconAvailable: boolean;
}

export interface ItemCatalogPage {
  records: ItemCatalogItem[];
  categories: ItemCatalogCategory[];
  pageNo: number;
  pageSize: number;
  total: number;
}

export interface ItemCatalogParams {
  keyword?: string;
  category?: string;
  pageNo?: number;
  pageSize?: number;
}

export function getItemCatalog(params: ItemCatalogParams) {
  return axios.get<ItemCatalogPage>('/setItem/v1/item/catalog', {
    params,
  });
}

/**
 * 获取物品图标URL
 * 优先使用本地图集，fallback 到 maplestory.io API
 */
export function getItemPreviewUrl(id: string | number): string {
  if (!id || Number(id) <= 0) return '';
  const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
  return `${apiBase}/assets/item-icons/${id}.png`;
}

/**
 * 获取 maplestory.io 图标地址
 */
function getMapleStoryIconUrl(id: number, version = '83'): string {
  return `https://maplestory.io/api/GMS/${version}/item/${id}/icon`;
}

/**
 * 物品图标加载失败时的 fallback
 * 本地图集 → maplestory.io GMS/255 → GMS/83 → 隐藏
 */
export function handleItemPreviewError(event: Event, id: number) {
  const img = event.target as HTMLImageElement;
  if (!img) return;

  // 使用 dataset 跟踪 fallback 状态
  if (!img.dataset.previewFallback) {
    img.dataset.previewFallback = 'modern';
    img.src = getMapleStoryIconUrl(id, '255');
    return;
  }
  if (img.dataset.previewFallback === 'modern') {
    img.dataset.previewFallback = 'legacy';
    img.src = getMapleStoryIconUrl(id, '83');
    return;
  }
  // 所有 fallback 失败，隐藏图片
  img.style.visibility = 'hidden';
}
