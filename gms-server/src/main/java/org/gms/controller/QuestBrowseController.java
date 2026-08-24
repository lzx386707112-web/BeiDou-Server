package org.gms.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.gms.constants.api.ApiConstant;
import org.gms.model.dto.*;
import org.gms.service.QuestBrowseService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 任务浏览：按 地区 → 城镇/街道 浏览任务（等级排序），查看任务详情（NPC / 内容 / 任务链）。
 */
@RestController
@AllArgsConstructor
@RequestMapping("/quest")
public class QuestBrowseController {

    private final QuestBrowseService questBrowseService;

    @Tag(name = "/quest/" + ApiConstant.LATEST)
    @Operation(summary = "获取任务地区树（大地区→城镇/街道，含任务数）")
    @GetMapping("/" + ApiConstant.LATEST + "/townTree")
    public ResultBody<List<MapTreeItemDTO>> townTree() {
        return ResultBody.success(questBrowseService.townTree());
    }

    @Tag(name = "/quest/" + ApiConstant.LATEST)
    @Operation(summary = "任务列表（按地区/城镇筛选，按等级排序）")
    @PostMapping("/" + ApiConstant.LATEST + "/list")
    public ResultBody<List<QuestSummaryDTO>> list(@RequestBody SubmitBody<QuestBrowseDTO> request) {
        QuestBrowseDTO dto = request.getData();
        String region = dto != null ? dto.getRegion() : null;
        String town = dto != null ? dto.getTown() : null;
        return ResultBody.success(request, questBrowseService.list(region, town));
    }

    @Tag(name = "/quest/" + ApiConstant.LATEST)
    @Operation(summary = "任务详情（NPC / 三段内容 / 任务链）")
    @PostMapping("/" + ApiConstant.LATEST + "/detail")
    public ResultBody<QuestDetailDTO> detail(@RequestBody SubmitBody<QuestBrowseDTO> request) {
        QuestBrowseDTO dto = request.getData();
        String questId = dto != null ? dto.getQuestId() : null;
        return ResultBody.success(request, questBrowseService.detail(questId));
    }
}
