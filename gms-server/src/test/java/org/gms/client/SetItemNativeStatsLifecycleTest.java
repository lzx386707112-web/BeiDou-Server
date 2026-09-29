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

    @SuppressWarnings({"rawtypes", "unchecked"})
    @Test
    void setBonusesRestoreRealBuffsAndClearWithoutChangingTheirExpiry() throws Exception {
        var constructor = Character.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Character character = spy(constructor.newInstance());
        Job beginner = Job.BEGINNER;
        doReturn(beginner).when(character).getJob();
        doNothing().when(character).sendPacket(any(Packet.class));
        var definition = new SetItemManager.Definition(20000, -1, "test", List.of(List.of(1002000)),
                List.of(new SetItemManager.Tier(1, Map.of("PDD", 30))), "test");
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
            assertArrayEquals(org.gms.util.PacketCreator.cancelBuff(List.of(BuffStat.WDEF)).getBytes(),
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
            ((Map) effects.get(character)).put(BuffStat.WDEF, holderConstructor.newInstance(effect, 0L, 20));
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
