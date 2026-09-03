package org.gms.client;

import org.gms.server.maps.MapObjectType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class HpMpExpansionTest {

    @Test
    void hpMpValuesRemainIntSizedAndStopAtFiftyThousand() {
        TestCharacterObject character = new TestCharacterObject();

        character.updateMaxHpMaxMp(32768, 40000);
        assertEquals(32768, character.getMaxHp());
        assertEquals(40000, character.getMaxMp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getClientMaxHp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getClientMaxMp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getCurrentMaxHp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getCurrentMaxMp());

        character.changeHpMp(50001, 50001, true);
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getHp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getMp());

        character.updateMaxHpMaxMp(50001, 60000);
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getMaxHp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getMaxMp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getClientMaxHp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getClientMaxMp());

        character.changeHpMp(50001, 50001, true);
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getHp());
        assertEquals(AbstractCharacterObject.MAX_HP_MP, character.getMp());
    }

    @Test
    void fullRecoveryUsesTheRaisedMaximumBeforeAFullStatRecalculation() {
        TestCharacterObject character = new TestCharacterObject();
        character.updateMaxHpMaxMp(32768, 40000);
        character.changeHpMp(40375, 34062, true);
        character.addHP(50000);
        character.addMP(50000);

        assertEquals(50000, character.getCurrentMaxHp());
        assertEquals(50000, character.getCurrentMaxMp());
        assertEquals(50000, character.getHp());
        assertEquals(50000, character.getMp());
    }

    private static final class TestCharacterObject extends AbstractCharacterObject {
        private TestCharacterObject() {
            setListener(new AbstractCharacterListener() {
                @Override
                public void onHpChanged(int oldHp) {
                }

                @Override
                public void onHpMpPoolUpdate() {
                }

                @Override
                public void onStatUpdate() {
                }

                @Override
                public void onAnnounceStatPoolUpdate() {
                }
            });
        }

        @Override
        public MapObjectType getType() {
            return MapObjectType.PLAYER;
        }

        @Override
        public void sendSpawnData(Client client) {
        }

        @Override
        public void sendDestroyData(Client client) {
        }
    }
}
