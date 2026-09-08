package org.gms.net.server.channel.handlers;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.client.inventory.BodyPart;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.constants.id.ItemId;
import org.gms.constants.skills.Beginner;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.server.maps.MapleMap;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.util.Locale;

import static java.util.concurrent.TimeUnit.MINUTES;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.RETURNS_MOCKS;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SpecialMoveHandlerFrenzyTotemTest {
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
    void successfulCastActivatesMapAndStartsStandardCooldown() {
        Character character = mock(Character.class);
        Client client = mock(Client.class);
        Inventory equipped = mock(Inventory.class);
        MapleMap map = mock(MapleMap.class);
        Item totem = new Item(ItemId.FRENZY_TOTEM, (short) -BodyPart.TOTEM.getValue(), (short) 1);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);
        when(equipped.getItem((short) -BodyPart.TOTEM.getValue())).thenReturn(totem);
        when(character.getMap()).thenReturn(map);
        when(map.activateFrenzyTotem(character)).thenReturn(true);

        SpecialMoveHandler.useFrenzyTotem(character, client);

        verify(map).activateFrenzyTotem(character);
        verify(character).addCooldown(
                org.mockito.ArgumentMatchers.eq(Beginner.FRENZY_TOTEM),
                anyLong(),
                org.mockito.ArgumentMatchers.eq(MINUTES.toMillis(20))
        );
    }

    @Test
    void failedActivationDoesNotStartCooldown() {
        Character character = mock(Character.class);
        Client client = mock(Client.class);
        Inventory equipped = mock(Inventory.class);
        MapleMap map = mock(MapleMap.class);
        Item totem = new Item(ItemId.FRENZY_TOTEM, (short) -BodyPart.TOTEM.getValue(), (short) 1);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);
        when(equipped.getItem((short) -BodyPart.TOTEM.getValue())).thenReturn(totem);
        when(character.getMap()).thenReturn(map);

        SpecialMoveHandler.useFrenzyTotem(character, client);

        verify(character, never()).addCooldown(
                org.mockito.ArgumentMatchers.anyInt(), anyLong(), anyLong()
        );
    }

    @Test
    void castWithoutEquippedTotemIsRejected() {
        Character character = mock(Character.class);
        Client client = mock(Client.class);
        Inventory equipped = mock(Inventory.class);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        SpecialMoveHandler.useFrenzyTotem(character, client);

        verify(character, never()).getMap();
        verify(character, never()).addCooldown(
                org.mockito.ArgumentMatchers.anyInt(), anyLong(), anyLong()
        );
    }
}
