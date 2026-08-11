package org.gms.constants.game;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ExpTableTest {

    @Test
    void postLevel200ExpRateDecreasesOnePercentPerLevelWithFiftyPercentFloor() {
        assertEquals(1.0f, ExpTable.getPostLevel200ExpRate(199));
        assertEquals(1.0f, ExpTable.getPostLevel200ExpRate(200));
        assertEquals(0.99f, ExpTable.getPostLevel200ExpRate(201), 0.000001f);
        assertEquals(0.90f, ExpTable.getPostLevel200ExpRate(210), 0.000001f);
        assertEquals(0.80f, ExpTable.getPostLevel200ExpRate(220), 0.000001f);
        assertEquals(0.50f, ExpTable.getPostLevel200ExpRate(250), 0.000001f);
        assertEquals(0.50f, ExpTable.getPostLevel200ExpRate(255), 0.000001f);
    }
}
