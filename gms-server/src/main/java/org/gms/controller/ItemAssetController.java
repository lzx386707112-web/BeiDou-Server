package org.gms.controller;

import lombok.RequiredArgsConstructor;
import org.gms.service.ItemCatalogService;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/assets/item-icons")
@RequiredArgsConstructor
public class ItemAssetController {
    private final ItemCatalogService itemCatalogService;

    @GetMapping(value = "/{itemId}.png", produces = MediaType.IMAGE_PNG_VALUE)
    public ResponseEntity<byte[]> icon(@PathVariable int itemId) {
        byte[] icon = itemCatalogService.icon(itemId);
        if (icon == null || icon.length == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(1, TimeUnit.HOURS).cachePublic())
                .contentType(MediaType.IMAGE_PNG)
                .body(icon);
    }
}
