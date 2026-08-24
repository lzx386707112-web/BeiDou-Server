package org.gms.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.gms.constants.api.ApiConstant;
import org.gms.model.dto.*;
import org.gms.service.MapDetectService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@AllArgsConstructor
@RequestMapping("/map")
public class MapDetectController {

    private final MapDetectService mapDetectService;

    @Tag(name = "/map/" + ApiConstant.LATEST)
    @Operation(summary = "地图功能检测")
    @PostMapping("/" + ApiConstant.LATEST + "/detect")
    public ResultBody<MapDetectResultDTO> detect(@RequestBody SubmitBody<MapDetectDTO> request) {
        return ResultBody.success(request, mapDetectService.detect(request.getData().getMapId()));
    }

    @Tag(name = "/map/" + ApiConstant.LATEST)
    @Operation(summary = "地图对比（找崩溃点差异）")
    @PostMapping("/" + ApiConstant.LATEST + "/compare")
    public ResultBody<MapCompareResultDTO> compare(@RequestBody SubmitBody<MapDetectDTO> request) {
        MapDetectDTO dto = request.getData();
        return ResultBody.success(request, mapDetectService.compare(
                dto.getMapId(), dto.getMapId2()));
    }

    @Tag(name = "/map/" + ApiConstant.LATEST)
    @Operation(summary = "获取地图目录树（大地区→城镇→具体地图）")
    @GetMapping("/" + ApiConstant.LATEST + "/mapTree")
    public ResultBody<List<MapTreeItemDTO>> mapTree() {
        return ResultBody.success(mapDetectService.buildMapTree());
    }
}
