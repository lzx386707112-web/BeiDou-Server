package org.gms.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.gms.constants.api.ApiConstant;
import org.gms.model.dto.*;
import org.gms.service.DropService;
import org.gms.service.MobCatalogService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/mob")
public class MobController {
    private final MobCatalogService mobCatalogService;
    private final DropService dropService;

    @Tag(name = "/mob/" + ApiConstant.LATEST)
    @Operation(summary = "分页预览怪物目录")
    @GetMapping("/" + ApiConstant.LATEST + "/catalog")
    public ResultBody<MobCatalogPageDTO> catalog(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer pageNo,
            @RequestParam(required = false) Integer pageSize,
            @RequestParam(required = false) Integer minLevel,
            @RequestParam(required = false) Integer maxLevel) {
        return ResultBody.success(mobCatalogService.catalog(keyword, pageNo, pageSize, minLevel, maxLevel));
    }

    @Tag(name = "/mob/" + ApiConstant.LATEST)
    @Operation(summary = "获取怪物的掉落物列表")
    @GetMapping("/" + ApiConstant.LATEST + "/{mobId}/drops")
    public ResultBody<List<DropSearchRtnDTO>> getMobDrops(@PathVariable int mobId) {
        return ResultBody.success(dropService.getDropsByMobId(mobId));
    }

    @Tag(name = "/mob/" + ApiConstant.LATEST)
    @Operation(summary = "为怪物添加掉落物")
    @PutMapping("/" + ApiConstant.LATEST + "/{mobId}/drops")
    public ResultBody<Long> addMobDrop(@PathVariable int mobId,
                                       @RequestBody SubmitBody<DropSearchRtnDTO> request) {
        DropSearchRtnDTO data = request.getData();
        data.setDropperId(mobId);
        data.setId(null);
        return ResultBody.success(request, dropService.modifyDropData(data, false, false));
    }

    @Tag(name = "/mob/" + ApiConstant.LATEST)
    @Operation(summary = "删除怪物掉落物")
    @DeleteMapping("/" + ApiConstant.LATEST + "/drops/{dropId}")
    public ResultBody<Object> deleteMobDrop(@PathVariable long dropId) {
        dropService.modifyDropData(DropSearchRtnDTO.builder().id(dropId).build(), false, true);
        return ResultBody.success(null);
    }
}
