package org.gms.model.dto;

import lombok.Data;

import java.util.List;

/**
 * 地图检测：聚合后的"地图信息"详情（名字 / 地区 / 怪物 / NPC），便于前端直接展示。
 */
@Data
public class MapInfoDTO {
    /** 地图 ID */
    private String mapId;
    /** 地图名字（String.wz/Map.img 的 mapName） */
    private String name;
    /** 所在地区 / 街道名（String.wz/Map.img 的 streetName） */
    private String region;
    /** 该地图是否配置了怪物 */
    private boolean hasMonster;
    /** 怪物列表（去重后的 id + 中文名） */
    private List<MapDetectRefDTO> monsters;
    /** NPC 数量 */
    private int npcCount;
    /** NPC 列表（去重后的 id + 中文名） */
    private List<MapDetectRefDTO> npcs;
}
