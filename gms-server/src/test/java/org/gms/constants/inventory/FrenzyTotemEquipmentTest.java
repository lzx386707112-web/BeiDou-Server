package org.gms.constants.inventory;

import org.gms.client.inventory.BodyPart;
import org.gms.client.inventory.InventoryType;
import org.gms.constants.id.ItemId;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

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

class FrenzyTotemEquipmentTest {
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
    void nativeEquipmentIdUsesItsOwnTotemSlot() {
        assertEquals(1189999, ItemId.FRENZY_TOTEM);
        assertEquals(InventoryType.EQUIP, ItemConstants.getInventoryType(ItemId.FRENZY_TOTEM));
        assertEquals(InventoryType.SETUP, ItemConstants.getInventoryType(3019999));
        assertEquals(BodyPart.TOTEM.getValue(), ItemConstants.getEquipSlotType(ItemId.FRENZY_TOTEM));
        assertTrue(ItemConstants.isEquipment(ItemId.FRENZY_TOTEM));
        assertTrue(EquipSlot.TOTEM.isAllowed(-BodyPart.TOTEM.getValue(), false));
        assertFalse(ItemId.isChair(ItemId.FRENZY_TOTEM));
        assertTrue(ItemId.isChair(3019999));
    }

    @Test
    void existingExtendedEquipmentSlotsRemainUnchanged() {
        assertEquals(20, BodyPart.SHOULDER.getValue());
        assertEquals(51, BodyPart.SECONDARY_WEAPON.getValue());
        assertEquals(54, BodyPart.ROBOT_HEART.getValue());
        assertEquals(55, BodyPart.BADGE.getValue());
        assertEquals(56, BodyPart.EMBLEM.getValue());
    }
}
