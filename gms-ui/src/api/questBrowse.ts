import axios from 'axios';

export interface QuestTreeItem {
  value: string;
  label: string;
  count?: number;
  isLeaf?: boolean;
  children?: QuestTreeItem[];
}

export interface QuestSummary {
  questId: string;
  name: string;
  levelMin?: number;
  levelMax?: number;
  startNpcId?: string;
  startNpcName?: string;
  endNpcId?: string;
  endNpcName?: string;
  inChain?: boolean;
  region: string;
  town: string;
}

export interface QuestChainItem {
  questId: string;
  name: string;
  levelMin?: number;
  current?: boolean;
}

export interface QuestDetail {
  questId: string;
  name: string;
  levelMin?: number;
  levelMax?: number;
  startNpcId?: string;
  startNpcName?: string;
  endNpcId?: string;
  endNpcName?: string;
  contentStart?: string;
  contentProgress?: string;
  contentComplete?: string;
  parentName?: string;
  order?: number;
  chain: QuestChainItem[];
  region: string;
  town: string;
}

export function getQuestTownTree() {
  return axios.get('/quest/v1/townTree');
}

export function getQuestList(data: { region?: string; town?: string }) {
  return axios.post('/quest/v1/list', data);
}

export function getQuestDetail(data: { questId: string }) {
  return axios.post('/quest/v1/detail', data);
}
