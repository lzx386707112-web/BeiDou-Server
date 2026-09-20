package org.gms.net.server.channel.handlers;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SpiritCaliberReplayContractTest {
    @Test
    void spiritCaliberKeepsTmsStagesAndUsesCosmosStyleNumbers() throws Exception {
        String source = Files.readString(Path.of(
                "src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ));
        int start = source.indexOf("chr.sendPacket(PacketCreator.showEffect(SPIRIT_CALIBER_VIDEO_LAYER));");
        assertTrue(start >= 0);
        int end = source.indexOf("} else if (attack.skill == Hero.RAGE_UPRISING_VI)", start);
        assertTrue(end > start);
        String block = source.substring(start, end);
        assertTrue(block.contains("SPIRIT_CALIBER_TIMES_MS"));
        assertTrue(block.contains("SPIRIT_CALIBER_FINISH_TIMES_MS"));
        assertTrue(block.contains("SPIRIT_CALIBER_FINISH, true"));
        assertTrue(block.contains("SPIRIT_CALIBER_FINISH, false"));
        assertTrue(block.contains("LocalDamageNumberMode.INDEXED"));
        assertFalse(block.contains("LocalDamageNumberMode.TOTAL"));
        assertFalse(block.contains("damageMonster("));
        assertFalse(source.contains("FULLSCREEN_MCV_ATTACK_INTERVAL_MS"));
        assertFalse(source.contains("collectFullMapCloseTargets("));
        assertTrue(source.contains("840, 900, 960, 1020, 1080, 1140, 1200, 1260, 1320, 1380, 1440,"));
    }
}
