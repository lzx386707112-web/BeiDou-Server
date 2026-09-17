package org.gms.controller;

import lombok.RequiredArgsConstructor;
import org.gms.model.dto.ResultBody;
import org.gms.model.dto.SubmitBody;
import org.gms.model.dto.botcontrol.BotControlConfigDTO;
import org.gms.model.dto.botcontrol.BotControlStateDTO;
import org.gms.model.dto.botcontrol.BotControlUpdateDTO;
import org.gms.service.BotControlService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/bot-control/v1")
@PreAuthorize("hasRole('ADMIN')")
public class BotControlController {
    private final BotControlService botControlService;

    @GetMapping("/state")
    public ResultBody<BotControlStateDTO> state() {
        return ResultBody.success(botControlService.state());
    }

    @GetMapping("/config")
    public ResultBody<BotControlConfigDTO> config() {
        return ResultBody.success(botControlService.config());
    }

    @PutMapping("/config")
    public ResultBody<Integer> update(@RequestBody SubmitBody<BotControlUpdateDTO> request) {
        return ResultBody.success(request, botControlService.update(request.getData()));
    }

    @PostMapping("/market/start")
    public ResultBody<String> startMarket() {
        return ResultBody.success(botControlService.startMarket());
    }
}
