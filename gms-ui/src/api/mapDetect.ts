import axios from 'axios';

export interface MapDetectNode {
  category: string;
  refType: string;
  ref: string;
  status: 'OK' | 'WARN' | 'ERROR' | 'INFO';
  title: string;
  functionDesc: string;
  message: string;
  meta?: Record<string, string>;
  crashRisk?: string;
}

export interface MapDetectCategory {
  category: string;
  label: string;
  total: number;
  ok: number;
  warn: number;
  error: number;
  info: number;
  summaryOnly: boolean;
  nodes: MapDetectNode[];
}

export interface MapDetectResult {
  mapId: string;
  mapExists: boolean;
  total: number;
  ok: number;
  warn: number;
  error: number;
  info: number;
  crashRiskCount?: number;
  categories: MapDetectCategory[];
  mapInfo?: MapInfo;
  note?: string;
}

export interface MapDetectRef {
  id: string;
  name?: string;
}

export interface MapInfo {
  mapId: string;
  name?: string;
  region?: string;
  hasMonster: boolean;
  monsters?: MapDetectRef[];
  npcCount: number;
  npcs?: MapDetectRef[];
}

export interface MapTreeItem {
  value: string;
  label: string;
  count?: number;
  isLeaf?: boolean;
  children?: MapTreeItem[];
}

export function detectMap(data: { mapId: string }) {
  return axios.post('/map/v1/detect', data);
}

export function getMapTree() {
  return axios.get('/map/v1/mapTree');
}

export interface MapCompareDiff {
  category: string;
  description: string;
  valueA: string;
  valueB: string;
  crashRisk?: string;
}

export interface MapCompareInfo {
  mapId: string;
  mapExists: boolean;
  lifeCount: number;
  mobCount: number;
  npcCount: number;
  fhCount: number;
  portalCount: number;
  objCount: number;
  backCount: number;
  crashRiskCount: number;
  fileSize: number;
}

export interface MapCompareResult {
  mapIdA: string;
  mapIdB: string;
  infoA?: MapCompareInfo;
  infoB?: MapCompareInfo;
  diffs: MapCompareDiff[];
  crashSummary?: string;
}

export function compareMap(data: { mapId: string; mapId2: string }) {
  return axios.post('/map/v1/compare', data);
}
