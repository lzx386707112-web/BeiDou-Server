export interface DropState {
  id?: number;
  dropperId?: number;
  dropperName?: string;
  continent?: number;
  itemId?: number;
  itemName?: string;
  itemCategory?: string;  // 物品类别：装备、消耗、设置、其他、特殊、金币
  minimumQuantity?: number;
  maximumQuantity?: number;
  questId?: number;
  questName?: string;
  chance?: number;
  comments?: string;
}
