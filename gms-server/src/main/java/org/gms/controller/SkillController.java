package org.gms.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.gms.constants.api.ApiConstant;
import org.gms.exception.BizException;
import org.gms.model.dto.ResultBody;
import org.gms.model.dto.SkillCatalogItemDTO;
import org.gms.model.dto.SkillCatalogPageDTO;
import org.gms.model.dto.SkillJobCategoryDTO;
import org.gms.service.SkillCatalogService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/skill")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class SkillController {
    private final SkillCatalogService skillCatalogService;

    @Tag(name = "/skill/" + ApiConstant.LATEST)
    @Operation(summary = "分页预览职业技能")
    @GetMapping("/" + ApiConstant.LATEST + "/catalog")
    public ResultBody<SkillCatalogPageDTO> catalog(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer jobId,
            @RequestParam(required = false) Integer advancement,
            @RequestParam(required = false) Integer pageNo,
            @RequestParam(required = false) Integer pageSize) {
        return ResultBody.success(skillCatalogService.catalog(keyword, jobId, advancement, pageNo, pageSize));
    }

    @Tag(name = "/skill/" + ApiConstant.LATEST)
    @Operation(summary = "获取单个技能详情")
    @GetMapping("/" + ApiConstant.LATEST + "/detail/{skillId}")
    public ResultBody<SkillCatalogItemDTO> detail(@PathVariable int skillId) {
        SkillCatalogItemDTO skill = skillCatalogService.getSkill(skillId);
        if (skill == null) {
            throw BizException.illegalArgument("技能不存在: " + skillId);
        }
        return ResultBody.success(skill);
    }

    @Tag(name = "/skill/" + ApiConstant.LATEST)
    @Operation(summary = "获取职业分类列表")
    @GetMapping("/" + ApiConstant.LATEST + "/jobs")
    public ResultBody<List<SkillJobCategoryDTO>> jobs() {
        return ResultBody.success(skillCatalogService.getJobCategories());
    }

    @Tag(name = "/skill/" + ApiConstant.LATEST)
    @Operation(summary = "重新加载技能目录")
    @PostMapping("/" + ApiConstant.LATEST + "/reload")
    public ResultBody<Integer> reload() {
        return ResultBody.success(skillCatalogService.reload());
    }
}
