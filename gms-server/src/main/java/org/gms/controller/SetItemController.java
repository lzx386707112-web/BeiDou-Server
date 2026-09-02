package org.gms.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.gms.constants.api.ApiConstant;
import org.gms.exception.BizException;
import org.gms.model.dto.ResultBody;
import org.gms.model.dto.SetItemConfigDTO;
import org.gms.model.dto.SetItemDefinitionCreateDTO;
import org.gms.model.dto.SetItemEnabledDTO;
import org.gms.model.dto.SetItemEquipmentDTO;
import org.gms.model.dto.EquipmentCatalogPageDTO;
import org.gms.model.dto.SetItemUpdateDTO;
import org.gms.model.dto.SubmitBody;
import org.gms.service.SetItemConfigService;
import org.gms.service.EquipmentCatalogService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/setItem")
public class SetItemController {
    private final SetItemConfigService setItemConfigService;
    private final EquipmentCatalogService equipmentCatalogService;

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "获取全部套装及当前档位属性")
    @GetMapping("/" + ApiConstant.LATEST + "/catalog")
    public ResultBody<List<SetItemConfigDTO>> catalog() {
        return ResultBody.success(setItemConfigService.catalog());
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "按名称或物品ID模糊搜索装备")
    @GetMapping("/" + ApiConstant.LATEST + "/equipment/search")
    public ResultBody<List<SetItemEquipmentDTO>> searchEquipment(
            @RequestParam String keyword) {
        return ResultBody.success(setItemConfigService.searchEquipment(keyword));
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "分类分页预览装备及其基础属性")
    @GetMapping("/" + ApiConstant.LATEST + "/equipment/catalog")
    public ResultBody<EquipmentCatalogPageDTO> equipmentCatalog(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) Integer pageNo,
            @RequestParam(required = false) Integer pageSize,
            @RequestParam(required = false) Boolean cash,
            @RequestParam(required = false) String weaponType,
            @RequestParam(required = false) Integer job,
            @RequestParam(required = false) Integer minLevel,
            @RequestParam(required = false) Integer maxLevel) {
        return ResultBody.success(equipmentCatalogService.catalog(
                keyword, category, pageNo, pageSize, cash, weaponType, job, minLevel, maxLevel));
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "新增自定义套装")
    @PostMapping("/" + ApiConstant.LATEST + "/custom")
    public ResultBody<Integer> create(
            @RequestBody SubmitBody<SetItemDefinitionCreateDTO> request) {
        return ResultBody.success(request,
                setItemConfigService.create(request.getData()));
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "停用或恢复内置套装效果")
    @PutMapping("/" + ApiConstant.LATEST + "/{definitionId}/enabled")
    public ResultBody<Integer> setEnabled(
            @PathVariable int definitionId,
            @RequestBody SubmitBody<SetItemEnabledDTO> request) {
        SetItemEnabledDTO data = request.getData();
        if (data == null || data.getEnabled() == null) {
            throw BizException.illegalArgument("启用状态不能为空");
        }
        return ResultBody.success(request, setItemConfigService.setBuiltInEnabled(
                definitionId, data.getEnabled()));
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "删除自定义套装")
    @DeleteMapping("/" + ApiConstant.LATEST + "/custom/{definitionId}")
    public ResultBody<Integer> deleteCustom(@PathVariable int definitionId) {
        return ResultBody.success(setItemConfigService.deleteCustom(definitionId));
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "更新一套装备的全部档位属性")
    @PutMapping("/" + ApiConstant.LATEST + "/{definitionId}")
    public ResultBody<Integer> update(@PathVariable int definitionId,
                                      @RequestBody SubmitBody<SetItemUpdateDTO> request) {
        return ResultBody.success(request,
                setItemConfigService.update(definitionId, request.getData()));
    }

    @Tag(name = "/setItem/" + ApiConstant.LATEST)
    @Operation(summary = "将套装属性重置为内置默认值")
    @DeleteMapping("/" + ApiConstant.LATEST + "/{definitionId}")
    public ResultBody<Integer> reset(@PathVariable int definitionId) {
        return ResultBody.success(setItemConfigService.reset(definitionId));
    }
}
