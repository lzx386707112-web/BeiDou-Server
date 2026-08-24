package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 地图目录树节点（三级：大地区 → 城镇/街道 → 具体地图）。
 *
 * <p>数据来源：String.wz/Map.img.xml。value 规则：
 * <ul>
 *   <li>大地区：地区 key（如 victoria / ossyria）</li>
 *   <li>城镇/街道：地区key/街道名（保证跨地区同名街道不冲突）</li>
 *   <li>具体地图：9 位补零地图 id（与 Map.wz 文件名一致，可直接用于 detect）</li>
 * </ul>
 * </p>
 */
@Data
public class MapTreeItemDTO {
    /** 节点值 */
    private String value;
    /** 显示名（地区/街道含数量，地图含 id） */
    private String label;
    /** 直接子节点数（仅地区/街道层级） */
    private Integer count;
    /** 是否叶子节点（具体地图） */
    private Boolean isLeaf;
    /** 子节点 */
    private List<MapTreeItemDTO> children;
}
