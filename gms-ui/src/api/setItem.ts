import axios from 'axios';

export const SET_ITEM_STAT_KEYS = [
  'STR',
  'DEX',
  'INT',
  'LUK',
  'PAD',
  'MAD',
  'PDD',
  'MDD',
  'ACC',
  'EVA',
  'HP',
  'MP',
  'FinalDamage',
  'BossDamage',
  'ExpRate',
  'DropRate',
  'MesoRate',
] as const;

export const SET_ITEM_PERCENT_BASES = SET_ITEM_STAT_KEYS.slice(0, 12);
export const setItemStatBase = (key: string) => key.replace(/Pct$/, '');
export const setItemStatIsPercent = (key: string) =>
  key.endsWith('Pct') || key.endsWith('Rate') || key.endsWith('Damage');
export const setItemStatMaximum = (key: string) =>
  setItemStatIsPercent(key) ? 10000 : 1000000;

export interface SetItemTier {
  requiredCount: number;
  stats: Record<string, number>;
  defaultStats: Record<string, number>;
  customized: boolean;
}

export interface SetItemEquipment {
  id: number;
  name: string;
}

export interface SetItemDefinition {
  id: number;
  jobIndex: number;
  name: string;
  completeCount: number;
  builtIn: boolean;
  enabled: boolean;
  slots: SetItemEquipment[][];
  defaultSlots: SetItemEquipment[][];
  slotsCustomized: boolean;
  tiers: SetItemTier[];
}

export interface SetItemDefinitionCreate {
  name: string;
  jobIndex: number;
  slots: number[][];
  tiers: Record<number, Record<string, number>>;
}

export function getSetItemCatalog() {
  return axios.get<SetItemDefinition[]>('/setItem/v1/catalog');
}

export function updateSetItem(
  definitionId: number,
  tiers: Record<number, Record<string, number>>,
  slots?: number[][]
) {
  return axios.put<number>(`/setItem/v1/${definitionId}`, { tiers, slots });
}

export function resetSetItem(definitionId: number) {
  return axios.delete<number>(`/setItem/v1/${definitionId}`);
}

export function searchSetItemEquipment(keyword: string) {
  return axios.get<SetItemEquipment[]>('/setItem/v1/equipment/search', {
    params: { keyword },
  });
}

export function createSetItem(data: SetItemDefinitionCreate) {
  return axios.post<number>('/setItem/v1/custom', data);
}

export function setBuiltInSetItemEnabled(
  definitionId: number,
  enabled: boolean
) {
  return axios.put<number>(`/setItem/v1/${definitionId}/enabled`, {
    enabled,
  });
}

export function deleteCustomSetItem(definitionId: number) {
  return axios.delete<number>(`/setItem/v1/custom/${definitionId}`);
}
