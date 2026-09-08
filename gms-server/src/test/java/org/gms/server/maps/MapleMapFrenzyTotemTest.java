package org.gms.server.maps;

import org.gms.client.Character;
import org.gms.constants.skills.Beginner;
import org.gms.manager.ServerManager;
import org.gms.net.packet.Packet;
import org.gms.property.ServiceProperty;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.awt.Point;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.RETURNS_MOCKS;
import static org.mockito.Mockito.when;

class MapleMapFrenzyTotemTest {
    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class, RETURNS_MOCKS);
        ServiceProperty serviceProperty = new ServiceProperty();
        serviceProperty.setLanguage("zh-CN");
        MessageSource messageSource = mock(MessageSource.class);
        when(messageSource.getMessage(anyString(), any(Object[].class), any(Locale.class)))
                .thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(serviceProperty);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messageSource);
        new ServerManager().setApplicationContext(context);
    }

    @Test
    void frenzyTotemUsesTheStandardStationarySummonPacket() {
        Character owner = mock(Character.class);
        Summon summon = mock(Summon.class);
        when(owner.getId()).thenReturn(1234);
        when(summon.getOwner()).thenReturn(owner);
        when(summon.getObjectId()).thenReturn(5678);
        when(summon.getSkill()).thenReturn(Beginner.FRENZY_TOTEM);
        when(summon.getSkillLevel()).thenReturn((byte) 1);
        when(summon.getPosition()).thenReturn(new Point(10, 20));
        when(summon.getMovementType()).thenReturn(SummonMovementType.STATIONARY);

        Packet packet = org.gms.util.PacketCreator.spawnSummon(summon, true);
        byte[] bytes = packet.getBytes();

        assertEquals(Beginner.FRENZY_TOTEM,
                ByteBuffer.wrap(bytes, 10, 4).order(ByteOrder.LITTLE_ENDIAN).getInt());
        assertEquals(SummonMovementType.STATIONARY.getValue(), bytes[23]);
        assertEquals(1, bytes[24]);
    }

    @Test
    void frenzyTotemIsClassifiedAsAStationarySummon() {
        Character owner = mock(Character.class);
        when(owner.getSkillLevel((org.gms.client.Skill) null)).thenReturn((byte) 1);

        Summon summon = new Summon(
                owner,
                Beginner.FRENZY_TOTEM,
                new Point(10, 20),
                SummonMovementType.STATIONARY
        );

        assertTrue(summon.isStationary());
        assertTrue(summon.canAttack());
    }

    @Test
    void frenzyTotemUsesAllDuplicatedSpawnPointsAsItsTarget() {
        assertEquals(3, MapleMap.calculateNumShouldSpawn(4, 0, 1, false, false));
        assertEquals(8, MapleMap.calculateNumShouldSpawn(8, 0, 1, false, true));
        assertEquals(3, MapleMap.calculateNumShouldSpawn(8, 5, 1, false, true));
    }

    @Test
    void normalSummonAttackCapabilityIsUnchanged() {
        Character owner = mock(Character.class);
        when(owner.getSkillLevel((org.gms.client.Skill) null)).thenReturn((byte) 1);

        Summon normalSummon = new Summon(
                owner,
                5211001,
                new Point(10, 20),
                SummonMovementType.STATIONARY
        );
        Summon puppet = new Summon(
                owner,
                3111002,
                new Point(10, 20),
                SummonMovementType.STATIONARY
        );

        assertTrue(normalSummon.canAttack());
        assertFalse(puppet.canAttack());
    }
}
