package org.gms.net.server.channel.handlers;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DarkKnightMcvReplayContractTest {
    @Test
    void deadSpaceKeepsTmsStagesAndUsesCosmosStyleNumbers() throws Exception {
        String source = Files.readString(Path.of(
                "src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ));
        int start = source.indexOf("chr.sendPacket(PacketCreator.showEffect(DEAD_SPACE_VIDEO_LAYER));");
        assertTrue(start >= 0);
        int end = source.indexOf("} else if (attack.skill == DarkKnight.DARK_HALIDOM)", start);
        assertTrue(end > start);
        String block = source.substring(start, end);
        assertTrue(block.contains("DEAD_SPACE_TIMES_MS"));
        assertTrue(block.contains("DEAD_SPACE_FINISH_TIMES_MS"));
        assertTrue(block.contains("DEAD_SPACE_FINISH, true"));
        assertTrue(block.contains("DEAD_SPACE_FINISH, false"));
        assertTrue(block.contains("LocalDamageNumberMode.INDEXED"));
        assertFalse(block.contains("LocalDamageNumberMode.TOTAL"));
        assertFalse(block.contains("damageMonster("));
        assertTrue(source.contains("collectMcvCloseTargets("));
        assertTrue(source.contains("originalEffect.applyTo(chr);"));
        assertFalse(source.contains("DEAD_SPACE_PULSE_HIT_COUNT"));
        assertFalse(source.contains("repeatFullscreenMcvPulse("));
    }

    @Test
    void darkHalidomKeepsTmsStagesAndUsesCosmosStyleNumbers() throws Exception {
        String source = Files.readString(Path.of(
                "src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ));
        int start = source.indexOf("chr.sendPacket(PacketCreator.showEffect(DARK_HALIDOM_VIDEO_LAYER));");
        assertTrue(start >= 0);
        int end = source.indexOf("} else if (attack.skill == DawnWarrior.GALAXY_STAR_BURST)", start);
        assertTrue(end > start);
        String block = source.substring(start, end);
        assertTrue(block.contains("DARK_HALIDOM_TIMES_MS"));
        assertTrue(block.contains("DARK_HALIDOM_FINISH_TIMES_MS"));
        assertTrue(block.contains("DARK_HALIDOM_FINISH, true"));
        assertTrue(block.contains("DARK_HALIDOM_FINISH, false"));
        assertTrue(block.contains("LocalDamageNumberMode.INDEXED"));
        assertFalse(block.contains("LocalDamageNumberMode.TOTAL"));
        assertFalse(block.contains("damageMonster("));
        assertTrue(source.contains("960, 1020, 1080, 1140, 1200, 1260, 1320, 1380, 1440, 1500, 1560, 1620"));
    }
}
