package org.gms.model.dto;

import lombok.Data;

import java.util.Map;

/**
 * 地图检测：单个节点（或单条引用）的检测结果
 */
@Data
public class MapDetectNodeDTO {
    /** 所属分类（info / npc / mob / reactor / portal / obj / tile / foothold / script / back） */
    private String category;
    /** 引用类型（npc / mob / reactor / portal / back / obj / tile / bgm / map / script / foothold ...） */
    private String refType;
    /** 被引用的资源标识（id 或名称，如 2143003 / Bgm25/timeGate / enH0） */
    private String ref;
    /** 状态：OK / WARN / ERROR / INFO */
    private String status;
    /** 标题（便于直接展示，如 "NPC 2143003"） */
    private String title;
    /** 该节点的作用说明（标记节点是干什么的） */
    private String functionDesc;
    /** 问题说明（无问题时为空） */
    private String message;
    /** 附加信息（x/y/fh/tm 等） */
    private Map<String, String> meta;
    /** 崩溃风险：null=无风险，CRASH=极可能导致客户端崩溃，DEGRADED=功能异常但不太会崩溃 */
    private String crashRisk;
}
