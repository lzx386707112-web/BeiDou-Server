package org.gms.server.life;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PartyGrindCompatTest {
    @Test
    void thirtyMinutesFiveBotsAndNoStack() {
        assertEquals(2431159, PartyGrindCompat.ITEM_ID);
        assertEquals(5, PartyGrindCompat.BOT_COUNT);
        assertEquals(30 * 60 * 1000L, PartyGrindCompat.DURATION_MS);
        assertTrue(PartyGrindCompat.canStart(false));
        assertFalse(PartyGrindCompat.canStart(true));
        assertFalse(PartyGrindCompat.hasParty(false));
        assertTrue(PartyGrindCompat.hasParty(true));
    }

    @Test
    void soloPartyHasFiveSlotsOthersDoNot() {
        assertTrue(PartyGrindCompat.canSummonFive(1));
        assertFalse(PartyGrindCompat.canSummonFive(0));
        assertFalse(PartyGrindCompat.canSummonFive(2));
        assertEquals(5, PartyGrindCompat.freeSlots(1));
        assertEquals(0, PartyGrindCompat.freeSlots(6));
    }

    @Test
    void expiresAtDeadline() {
        long expireAt = 1_800_000L;
        assertTrue(PartyGrindCompat.isActive(expireAt - 1, expireAt));
        assertFalse(PartyGrindCompat.isActive(expireAt, expireAt));
    }

    @Test
    void companionLevelFollowsLeaderPlusMinusThreeCappedAt255() {
        assertEquals(47, PartyGrindCompat.companionLevel(50, -3));
        assertEquals(53, PartyGrindCompat.companionLevel(50, 3));
        assertEquals(1, PartyGrindCompat.companionLevel(1, -3));
        assertEquals(255, PartyGrindCompat.companionLevel(255, 3));
        assertEquals(255, PartyGrindCompat.companionLevel(254, 3));
    }

    @Test
    void fiveBotsSpreadAcrossFloorsRoundRobin() {
        assertEquals(0, PartyGrindCompat.floorIndex(0, 1));
        assertEquals(0, PartyGrindCompat.floorIndex(4, 1));
        assertEquals(0, PartyGrindCompat.floorIndex(0, 3));
        assertEquals(1, PartyGrindCompat.floorIndex(1, 3));
        assertEquals(2, PartyGrindCompat.floorIndex(2, 3));
        assertEquals(0, PartyGrindCompat.floorIndex(3, 3));
        assertEquals(1, PartyGrindCompat.floorIndex(4, 3));
        assertEquals(0, PartyGrindCompat.floorIndex(0, 0));
    }
}
