package org.gms.net.server.channel.handlers;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SwordIllusionIndexedReplayContractTest {
    @Test
    void swordIllusionReplayKeepsCloseRangePacketsWithoutF6Supplement() throws Exception {
        Path path = Path.of("src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java");
        String source = Files.readString(path);
        int start = source.indexOf("} else if (attack.skill == Hero.SWORD_ILLUSION)");
        assertTrue(start >= 0);
        int end = source.indexOf("} else if (attack.skill == Hero.DEATH_FAULT)", start);
        assertTrue(end > start);
        String block = source.substring(start, end);
        assertTrue(block.contains("SWORD_ILLUSION_SLASH"));
        assertTrue(block.contains("SWORD_ILLUSION_EXPLOSION"));
        assertFalse(block.contains("LocalDamageNumberMode.INDEXED"));
        assertFalse(block.contains("LocalDamageNumberMode.TOTAL"));
        assertFalse(block.contains("SWORD_ILLUSION_SLASH, true"));
        assertTrue(block.contains("SWORD_ILLUSION_SLASH, false"));
        assertTrue(source.contains("collectSwordIllusionTargets("));
        assertTrue(source.contains("isWithinAttackBox(chr, monster, targetingEffect, attack, null, null)"));
        assertTrue(source.contains("Math.max(1, Math.min(8, originalEffect.getMobCount()))"));
        assertFalse(block.contains("damageMonster("));
        String abstractHandler = Files.readString(Path.of(
                "src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java"
        ));
        assertTrue(abstractHandler.contains("INDEXED_DAMAGE_NUMBER_HIT_INTERVAL_MS = 120"));
    }
}
