import axios from 'axios';

export interface EquipmentCatalogCategory {
  key: string;
  count: number;
}

export interface EquipmentCatalogItem {
  id: number;
  name: string;
  description: string;
  category: string;
  stats: Record<string, number>;
  iconAvailable: boolean;
}

export interface EquipmentCatalogPage {
  records: EquipmentCatalogItem[];
  categories: EquipmentCatalogCategory[];
  pageNo: number;
  pageSize: number;
  total: number;
  weaponTypes: EquipmentCatalogCategory[];
  cashCount: number;
  nonCashCount: number;
}

export interface EquipmentCatalogParams {
  keyword?: string;
  category?: string;
  pageNo?: number;
  pageSize?: number;
  cash?: boolean;
  weaponType?: string;
}

export function getEquipmentCatalog(params: EquipmentCatalogParams) {
  return axios.get<EquipmentCatalogPage>('/setItem/v1/equipment/catalog', {
    params,
  });
}
