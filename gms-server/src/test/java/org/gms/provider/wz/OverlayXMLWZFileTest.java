package org.gms.provider.wz;

import org.gms.provider.DataProvider;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OverlayXMLWZFileTest {
    @Test
    void stringOverlayLoadsChineseMapNames() {
        DataProvider strings = new OverlayXMLWZFile(
                Path.of("wz/String.wz"), Path.of("wz-zh-CN/String.wz"));
        assertNotNull(strings.getData("Map.img"));
        assertTrue(strings.getRoot().getFiles().stream()
                .anyMatch(file -> "Map.img".equals(file.getName())));
    }

    @Test
    void emptyMapOverlayFallsBackToBaseTownMaps(@TempDir Path emptyOverlay) {
        DataProvider maps = new OverlayXMLWZFile(Path.of("wz/Map.wz"), emptyOverlay);
        assertNotNull(maps.getData("Map/Map2/200000132.img"));
        assertNotNull(maps.getData("Map/Map3/350160240.img"));
    }
}
