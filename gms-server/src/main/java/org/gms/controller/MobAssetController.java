package org.gms.controller;

import lombok.RequiredArgsConstructor;
import org.gms.service.MobCatalogService;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/assets/mob-icons")
@RequiredArgsConstructor
public class MobAssetController {
    private final MobCatalogService mobCatalogService;

    @GetMapping(value = "/{mobId}.png", produces = MediaType.IMAGE_PNG_VALUE)
    public ResponseEntity<byte[]> icon(@PathVariable int mobId) {
        byte[] icon = mobCatalogService.icon(mobId);
        if (icon == null || icon.length == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(1, TimeUnit.HOURS).cachePublic())
                .contentType(MediaType.IMAGE_PNG)
                .body(icon);
    }
}
