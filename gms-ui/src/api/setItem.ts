import axios from 'axios';

export const SET_ITEM_STAT_KEYS = [
  'STR',
  'DEX',
  'INT',
  'LUK',
  'PAD',
  'MAD',
  'HP',
  'MP',
  'FinalDamage',
  'BossDamage',
  'ExpRate',
  'DropRate',
  'MesoRate',
] as const;

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
  tiers: Record<number, Record<string, number>>
) {
  return axios.put<number>(`/setItem/v1/${definitionId}`, { tiers });
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
