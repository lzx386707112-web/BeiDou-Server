package org.gms.controller;

import lombok.RequiredArgsConstructor;
import org.gms.model.dto.ResultBody;
import org.gms.model.dto.SubmitBody;
import org.gms.model.dto.weather.WeatherConfigDTO;
import org.gms.model.dto.weather.WeatherConfigUpdateDTO;
import org.gms.model.dto.weather.WeatherOverrideDTO;
import org.gms.model.dto.weather.WeatherRegionDTO;
import org.gms.model.dto.weather.WeatherRegionUpdateDTO;
import org.gms.model.dto.weather.WeatherStateDTO;
import org.gms.service.WeatherConfigService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/weather/v1")
@PreAuthorize("hasRole('ADMIN')")
public class WeatherController {
    private final WeatherConfigService weatherConfigService;

    @GetMapping("/state")
    public ResultBody<WeatherStateDTO> state() { return ResultBody.success(weatherConfigService.state()); }

    @GetMapping("/config")
    public ResultBody<WeatherConfigDTO> config() { return ResultBody.success(weatherConfigService.config()); }

    @PutMapping("/config")
    public ResultBody<Integer> updateConfig(@RequestBody SubmitBody<WeatherConfigUpdateDTO> request) {
        return ResultBody.success(request, weatherConfigService.updateConfig(request.getData()));
    }

    @GetMapping("/regions")
    public ResultBody<List<WeatherRegionDTO>> regions() { return ResultBody.success(weatherConfigService.regions()); }

    @PutMapping("/regions/{region}")
    public ResultBody<Integer> updateRegion(@PathVariable String region,
            @RequestBody SubmitBody<WeatherRegionUpdateDTO> request) {
        return ResultBody.success(request, weatherConfigService.updateRegion(region, request.getData()));
    }

    @PostMapping("/override")
    public ResultBody<Integer> override(@RequestBody SubmitBody<WeatherOverrideDTO> request) {
        return ResultBody.success(request, weatherConfigService.override(request.getData()));
    }

    @DeleteMapping("/override")
    public ResultBody<Integer> clearOverride() { return ResultBody.success(weatherConfigService.clearOverride()); }

    @PostMapping("/broadcast")
    public ResultBody<Integer> broadcast() { return ResultBody.success(weatherConfigService.broadcast()); }
}
