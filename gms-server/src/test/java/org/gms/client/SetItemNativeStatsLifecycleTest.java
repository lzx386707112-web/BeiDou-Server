package org.gms.client;

import org.gms.manager.ServerManager;
import org.gms.net.packet.Packet;
import org.gms.net.server.Server;
import org.gms.property.ServiceProperty;
import org.gms.server.SetItemBonusOverrides;
import org.gms.server.SetItemManager;
import org.gms.server.StatEffect;
import org.gms.server.ItemInformationProvider;
import org.gms.provider.DataProvider;
import org.gms.provider.DataProviderFactory;
import org.gms.provider.wz.WZFiles;
import org.gms.util.DatabaseConnection;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.gms.server.SetItemNativeStats;
import org.mockito.ArgumentCaptor;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.lang.reflect.Field;
import java.sql.Connection;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.List;
import java.util.Map;
import java.util.Locale;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SetItemNativeStatsLifecycleTest {
    @BeforeAll
    static void context() throws Exception {
        ApplicationContext context = mock(ApplicationContext.class);
        ServiceProperty property = new ServiceProperty();
        property.setLanguage("zh-CN");
        MessageSource messages = mock(MessageSource.class);
        when(messages.getMessage(anyString(), any(Object[].class), any(Locale.class))).thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(property);
        when(context.getBean(org.gms.service.ConfigService.class))
                .thenReturn(mock(org.gms.service.ConfigService.class));
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messages);
        new ServerManager().setApplicationContext(context);
        Connection connection = mock(Connection.class, RETURNS_DEEP_STUBS);
        DataProvider provider = mock(DataProvider.class, RETURNS_MOCKS);
        try (var db = mockStatic(DatabaseConnection.class);
             var providers = mockStatic(DataProviderFactory.class)) {
            db.when(DatabaseConnection::getConnection).thenReturn(connection);
            providers.when(() -> DataProviderFactory.getDataProvider(any(WZFiles.class))).thenReturn(provider);
            Class.forName(ItemInformationProvider.class.getName());
        }
    }

    @Test
    void realBlackGateHpMpBonusesRecalculateAndCapWithoutCompounding() throws Exception {
        var constructor = Character.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Character character = spy(constructor.newInstance());
        doNothing().when(character).sendPacket(any(Packet.class));
        doNothing().when(character).hpChangeAction(anyInt());
        character.setMaxHp(10000);
        character.setMaxMp(20000);
        var inventory = character.getInventory(org.gms.client.inventory.InventoryType.EQUIPPED);
        var blackGate = SetItemManager.builtInDefinitions().stream()
                .filter(set -> set.name().equals("黑门")).findFirst().orElseThrow();
        for (int i = 0; i < 5; i++) {
            var equip = new org.gms.client.inventory.Equip(blackGate.slots().get(i).getFirst(), (short) (-i - 1));
            equip.setHp((short) 100);
            equip.setMp((short) 200);
            inventory.addItemFromDB(equip);
        }
        character.reapplyLocalStats();
        assertPools(character, 10710, 21420, 10210, 20420);
        character.reapplyLocalStats();
        assertPools(character, 10710, 21420, 10210, 20420);
        assertEquals(10000, character.getMaxHp());
        assertEquals(20000, character.getMaxMp());
        try (var config = mockStatic(org.gms.config.GameConfig.class)) {
            character.hp = 1;
            character.mp = 1;
            character.healHpMp();
            assertEquals(10710, character.getHp());
            assertEquals(21420, character.getMp());
        }

        doReturn(60).when(character).getBuffedValue(BuffStat.HYPERBODYHP);
        doReturn(60).when(character).getBuffedValue(BuffStat.HYPERBODYMP);
        character.reapplyLocalStats();
        assertPools(character, 17136, 34272, 10210, 20420);
        assertEquals(character.getCurrentMaxHp(), (character.getClientMaxHp() + 500) * 160 / 100);
        assertEquals(character.getCurrentMaxMp(), (character.getClientMaxMp() + 1000) * 160 / 100);
        doReturn((Integer) null).when(character).getBuffedValue(BuffStat.HYPERBODYHP);
        doReturn((Integer) null).when(character).getBuffedValue(BuffStat.HYPERBODYMP);
        character.setMaxHp(49000);
        character.setMaxMp(49500);
        character.reapplyLocalStats();
        assertPools(character, 50000, 50000, 49990, 50000);
        assertEquals(character.getCurrentMaxHp(), Math.min(50000, character.getClientMaxHp() + 500));
        assertEquals(character.getCurrentMaxMp(), Math.min(50000, character.getClientMaxMp() + 1000));

        for (short position = -1; position >= -5; position--) inventory.removeSlot(position);
        Field changed = Character.class.getDeclaredField("equipchanged");
        changed.setAccessible(true);
        changed.setBoolean(character, true);
        character.reapplyLocalStats();
        assertPools(character, 49000, 49500);
        assertEquals(0, character.getSetItemBonus("HPPct"));

        var huge = new SetItemManager.Definition(20000, -1, "overflow", List.of(List.of(1002000)),
                List.of(new SetItemManager.Tier(1, Map.of("HP", Integer.MAX_VALUE, "MP", Integer.MAX_VALUE,
                        "HPPct", 10000, "MPPct", 10000))), "test");
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(huge), Set.of(), Map.of());
        try {
            inventory.addItemFromDB(new org.gms.client.inventory.Equip(1002000, (short) -1));
            changed.setBoolean(character, true);
            doReturn(60).when(character).getBuffedValue(BuffStat.HYPERBODYHP);
            doReturn(60).when(character).getBuffedValue(BuffStat.HYPERBODYMP);
            character.reapplyLocalStats();
            assertPools(character, 50000, 50000);
        } finally {
            SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of());
        }
    }

    private static void assertPools(Character character, int hp, int mp) {
        assertPools(character, hp, mp, hp, mp);
    }

    private static void assertPools(Character character, int hp, int mp, int clientHp, int clientMp) {
        assertEquals(hp, character.getCurrentMaxHp());
        assertEquals(mp, character.getCurrentMaxMp());
        assertEquals(clientHp, character.getClientMaxHp());
        assertEquals(clientMp, character.getClientMaxMp());
    }

    @ParameterizedTest
    @CsvSource({"true,true", "false,true", "true,false", "false,false"})
    void silentLoginBuffRestoreDoesNotSendStatsBeforeCharacterData(boolean silent,
                                                                  boolean preserveRatio) throws Exception {
        var constructor = Character.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Character character = spy(constructor.newInstance());
        character.setListener(new CharacterListener(character));
        doNothing().when(character).sendPacket(any(Packet.class));
        doNothing().when(character).hpChangeAction(anyInt());
        character.setMaxHp(10000);
        character.setMaxMp(20000);
        character.hp = preserveRatio ? 5000 : 50000;
        character.mp = preserveRatio ? 10000 : 50000;
        character.reapplyLocalStats();

        StatEffect hyperBody = mock(StatEffect.class);
        when(hyperBody.getBuffSourceId()).thenReturn(1301007);
        when(hyperBody.getStatups()).thenReturn(List.of(new org.gms.util.Pair<>(BuffStat.HYPERBODYHP, 60)));
        when(hyperBody.isActive(character)).thenReturn(true);
        try (var config = mockStatic(org.gms.config.GameConfig.class)) {
            config.when(() -> org.gms.config.GameConfig.getServerBoolean("use_fixed_ratio_hpmp_update"))
                    .thenReturn(preserveRatio);
            character.registerEffect(hyperBody, 1000L, 60000L, silent);
        }
        assertPools(character, 16000, 20000, 10000, 20000);
        assertEquals(preserveRatio ? 8000 : 16000, character.getHp());
        assertEquals(preserveRatio ? 10000 : 20000, character.getMp());
        character.setName("LoginTest");
        var initialStats = org.gms.net.packet.OutPacket.create(org.gms.net.opcodes.SendOpcode.SET_FIELD);
        var encodeStats = org.gms.util.PacketCreator.class.getDeclaredMethod("addCharStats",
                org.gms.net.packet.OutPacket.class, Character.class);
        encodeStats.setAccessible(true);
        encodeStats.invoke(null, initialStats, character);
        ByteBuffer initialData = ByteBuffer.wrap(initialStats.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        initialData.position(64);
        assertEquals(character.getHp(), initialData.getInt());
        assertEquals(character.getClientMaxHp(), initialData.getInt());
        assertEquals(character.getMp(), initialData.getInt());
        assertEquals(character.getClientMaxMp(), initialData.getInt());
        ArgumentCaptor<Packet> packet = ArgumentCaptor.forClass(Packet.class);
        verify(character, atLeast(0)).sendPacket(packet.capture());
        var statPackets = packet.getAllValues().stream().filter(value -> {
            byte[] bytes = value.getBytes();
            return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getShort() == 0x1f;
        }).toList();
        assertEquals(silent ? 0 : 1, statPackets.size(),
                "login restores run before SET_FIELD; live buffs must still update HP");
        if (!silent) assertEquals(preserveRatio ? 11 : 15, statPackets.getFirst().getBytes().length);
    }

    @ParameterizedTest
    @ValueSource(booleans = {false, true})
    void maxPoolChangesAreSentRegardlessOfRatioRecoverySetting(boolean preserveRatio) throws Exception {
        var constructor = Character.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Character character = spy(constructor.newInstance());
        doNothing().when(character).hpChangeAction(anyInt());
        character.setMaxHp(10000);
        character.setMaxMp(20000);
        character.hp = 5000;
        character.mp = 10000;
        var blackGate = SetItemManager.builtInDefinitions().stream()
                .filter(set -> set.name().equals("黑门")).findFirst().orElseThrow();
        var inventory = character.getInventory(org.gms.client.inventory.InventoryType.EQUIPPED);
        for (int i = 0; i < 5; i++) inventory.addItemFromDB(new org.gms.client.inventory.Equip(
                blackGate.slots().get(i).getFirst(), (short) (-i - 1)));
        try (var config = mockStatic(org.gms.config.GameConfig.class)) {
            config.when(() -> org.gms.config.GameConfig.getServerBoolean("use_fixed_ratio_hpmp_update"))
                    .thenReturn(preserveRatio);
            var updates = character.recalcLocalStats();
            var values = updates.stream().collect(java.util.stream.Collectors.toMap(
                    org.gms.util.Pair::getLeft, org.gms.util.Pair::getRight));
            assertEquals(10200, values.get(Stat.MAXHP));
            assertEquals(20400, values.get(Stat.MAXMP));
            assertEquals(preserveRatio ? 5100 : 5000, character.getHp());
            assertEquals(preserveRatio ? 10200 : 10000, character.getMp());
            assertTrue(character.recalcLocalStats().isEmpty(), "unchanged maxima do not resend");
            for (short position = -1; position >= -5; position--) inventory.removeSlot(position);
            Field changed = Character.class.getDeclaredField("equipchanged");
            changed.setAccessible(true);
            changed.setBoolean(character, true);
            values = character.recalcLocalStats().stream().collect(java.util.stream.Collectors.toMap(
                    org.gms.util.Pair::getLeft, org.gms.util.Pair::getRight));
            assertEquals(10000, values.get(Stat.MAXHP));
            assertEquals(20000, values.get(Stat.MAXMP));
        }
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    @ParameterizedTest
    @EnumSource(value = BuffStat.class, names = {"WDEF", "SPEED", "JUMP"})
    void setBonusesRestoreRealBuffsAndClearWithoutChangingTheirExpiry(BuffStat stat) throws Exception {
        var constructor = Character.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Character character = spy(constructor.newInstance());
        Job beginner = Job.BEGINNER;
        doReturn(beginner).when(character).getJob();
        doNothing().when(character).sendPacket(any(Packet.class));
        var definition = new SetItemManager.Definition(20000, -1, "test", List.of(List.of(1002000)),
                List.of(new SetItemManager.Tier(1, Map.of(SetItemNativeStats.key(stat), 30))), "test");
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(definition), Set.of(), Map.of());
        character.getInventory(org.gms.client.inventory.InventoryType.EQUIPPED)
                .addItemFromDB(new org.gms.client.inventory.Equip(1002000, (short) -1));
        Field bonus = Character.class.getDeclaredField("setItemBonus");
        bonus.setAccessible(true);
        bonus.set(character, SetItemManager.compute(character).bonus());
        Server server = mock(Server.class);
        when(server.getCurrentTime()).thenReturn(1000L);
        try (var servers = mockStatic(Server.class)) {
            servers.when(Server::getInstance).thenReturn(server);
            character.syncSetItemNativeStats();
            ArgumentCaptor<Packet> packet = ArgumentCaptor.forClass(Packet.class);
            verify(character).sendPacket(packet.capture());
            ByteBuffer data = ByteBuffer.wrap(packet.getValue().getBytes()).order(ByteOrder.LITTLE_ENDIAN);
            data.position(18);
            assertEquals(30, data.getShort());
            assertEquals(0, data.getInt());
            clearInvocations(character);
            bonus.set(character, SetItemManager.Bonus.NONE);
            character.syncSetItemNativeStats();
            verify(character).sendPacket(packet.capture());
            assertArrayEquals(org.gms.util.PacketCreator.cancelBuff(List.of(stat)).getBytes(),
                    packet.getValue().getBytes());
            bonus.set(character, SetItemManager.compute(character).bonus());
            clearInvocations(character);
            StatEffect effect = mock(StatEffect.class);
            when(effect.getBuffSourceId()).thenReturn(1001003);
            Class<?> holderClass = Class.forName("org.gms.client.Character$BuffStatValueHolder");
            var holderConstructor = holderClass.getDeclaredConstructor(StatEffect.class, long.class, int.class);
            holderConstructor.setAccessible(true);
            Field effects = Character.class.getDeclaredField("effects");
            effects.setAccessible(true);
            ((Map) effects.get(character)).put(stat, holderConstructor.newInstance(effect, 0L, 20));
            Field expires = Character.class.getDeclaredField("buffExpires");
            expires.setAccessible(true);
            ((Map) expires.get(character)).put(1001003, 3000L);
            character.syncSetItemNativeStats();
            verify(character).sendPacket(packet.capture());
            data = ByteBuffer.wrap(packet.getValue().getBytes()).order(ByteOrder.LITTLE_ENDIAN);
            data.position(18);
            assertEquals(50, data.getShort());
            assertEquals(1001003, data.getInt());
            assertEquals(2000, data.getInt());
            clearInvocations(character);
            bonus.set(character, SetItemManager.Bonus.NONE);
            character.syncSetItemNativeStats();
            verify(character).sendPacket(packet.capture());
            data = ByteBuffer.wrap(packet.getValue().getBytes()).order(ByteOrder.LITTLE_ENDIAN);
            data.position(18);
            assertEquals(20, data.getShort());
            assertEquals(1001003, data.getInt());
            assertEquals(2000, data.getInt());
            assertEquals(3000L, ((Map) expires.get(character)).get(1001003));
            clearInvocations(character);
            character.syncSetItemNativeStats();
            verify(character, never()).sendPacket(any());
        } finally {
            SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of());
        }
    }
}
