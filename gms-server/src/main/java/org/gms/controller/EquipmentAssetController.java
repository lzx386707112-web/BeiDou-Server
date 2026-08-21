package org.gms.controller;

import lombok.RequiredArgsConstructor;
import org.gms.service.EquipmentCatalogService;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/assets/equipment-icons")
@RequiredArgsConstructor
public class EquipmentAssetController {
    private final EquipmentCatalogService equipmentCatalogService;

    @GetMapping(value = "/{itemId}.png", produces = MediaType.IMAGE_PNG_VALUE)
    public ResponseEntity<byte[]> icon(@PathVariable int itemId) {
        byte[] icon = equipmentCatalogService.icon(itemId);
        if (icon == null || icon.length == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(1, TimeUnit.HOURS).cachePublic())
                .contentType(MediaType.IMAGE_PNG)
                .body(icon);
    }
}
