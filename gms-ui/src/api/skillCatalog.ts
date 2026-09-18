import axios from 'axios';

export interface SkillJobCategory {
  jobId: number;
  jobName: string;
  count: number;
}

export interface SkillCatalogItem {
  id: number;
  name: string;
  desc: string;
  jobName: string;
  jobId: number;
  maxLevel: number;
  iconAvailable: boolean;
  attributes: Record<string, any>;
  levelDescs: string[];
}

export interface SkillCatalogPage {
  records: SkillCatalogItem[];
  jobs: SkillJobCategory[];
  pageNo: number;
  pageSize: number;
  total: number;
  loaded?: boolean;
  message?: string;
}

export interface SkillCatalogParams {
  keyword?: string;
  jobId?: number;
  advancement?: number;
  pageNo?: number;
  pageSize?: number;
}

/**
 * 获取技能目录
 */
export function getSkillCatalog(params: SkillCatalogParams) {
  return axios.get<SkillCatalogPage>('/skill/v1/catalog', {
    params,
  });
}

/**
 * 获取单个技能详情
 */
export function getSkillDetail(skillId: number) {
  return axios.get<SkillCatalogItem>(`/skill/v1/detail/${skillId}`);
}

/**
 * 获取职业分类列表
 */
export function getSkillJobCategories() {
  return axios.get<SkillJobCategory[]>('/skill/v1/jobs');
}

/**
 * 重新加载技能目录
 */
export function reloadSkillCatalog() {
  return axios.post('/skill/v1/reload');
}

/**
 * 获取技能图标URL（本地图集）
 */
export function getSkillIconUrl(skillId: number): string {
  if (!skillId || skillId <= 0) return '';
  const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
  return `${apiBase}/assets/skill-icons/${skillId}.png`;
}

/**
 * 技能图标加载失败时的 fallback
 */
export function handleSkillIconError(event: Event, skillId: number) {
  const img = event.target as HTMLImageElement;
  if (!img) return;

  if (!img.dataset.iconFallback) {
    img.dataset.iconFallback = 'modern';
    img.src = `https://maplestory.io/api/GMS/83/skill/${skillId}/icon`;
    return;
  }
  if (img.dataset.iconFallback === 'modern') {
    img.dataset.iconFallback = 'legacy';
    img.src = `https://maplestory.io/api/GMS/255/skill/${skillId}/icon`;
    return;
  }
  img.style.visibility = 'hidden';
}
