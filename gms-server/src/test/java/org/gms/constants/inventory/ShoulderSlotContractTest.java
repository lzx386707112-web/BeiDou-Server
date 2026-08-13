package org.gms.constants.inventory;

import org.gms.client.Job;
import org.gms.client.inventory.BodyPart;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
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
import static org.mockito.Mockito.when;

class ShoulderSlotContractTest {
    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class);
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
    void shoulderUsesTheLegacyMobEquipBodyPart() {
        assertEquals(20, BodyPart.SHOULDER.getValue());
        assertEquals(20, ItemConstants.getEquipSlotType(1152081));
        assertTrue(EquipSlot.getFromTextSlot("Sh").isAllowed(-20, false));
        assertFalse(EquipSlot.getFromTextSlot("Sh").isAllowed(-51, false));
        assertEquals(EquipType.SHOULDER, EquipType.getEquipTypeById(1152081));
    }

    @Test
    void existingExtendedPendantAndSecondaryWeaponContractsRemainDistinct() {
        assertEquals(61, BodyPart.PENDANT_EXT.getValue());
        assertEquals(51, BodyPart.SECONDARY_WEAPON.getValue());
        assertEquals(BodyPart.SECONDARY_WEAPON.getValue(), ItemConstants.getEquipSlotType(1342000));
        assertEquals(BodyPart.SECONDARY_WEAPON.getValue(), ItemConstants.getEquipSlotType(1352206));
        assertTrue(EquipSlot.SECONDARY_WEAPON.isAllowed(-51, false));
        assertFalse(EquipSlot.SECONDARY_WEAPON.isAllowed(-10, false));
        assertEquals(EquipType.KATARA, EquipType.getEquipTypeById(1342000));
        assertEquals(EquipType.SECONDARY_WEAPON, EquipType.getEquipTypeById(1352206));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1342000, Job.BANDIT));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1342000, Job.CHIEFBANDIT));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1342000, Job.SHADOWER));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1342000, Job.ASSASSIN));
        assertEquals(EquipType.BELT, EquipType.getEquipTypeById(1132000));
    }

    @Test
    void secondaryWeaponsAreRestrictedToTheirExactExplorerOrCygnusBranch() {
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352206, Job.HERO));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352206, Job.PALADIN));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352216, Job.PALADIN));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352226, Job.DARKKNIGHT));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352236, Job.FP_ARCHMAGE));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352246, Job.IL_ARCHMAGE));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352256, Job.BISHOP));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352266, Job.BOWMASTER));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352276, Job.MARKSMAN));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352286, Job.BANDIT));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352286, Job.SHADOWER));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352296, Job.ASSASSIN));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352296, Job.HERMIT));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352296, Job.NIGHTLORD));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352906, Job.BUCCANEER));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352916, Job.CORSAIR));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352975, Job.DAWNWARRIOR4));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352975, Job.BLAZEWIZARD4));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352975, Job.WINDARCHER4));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352975, Job.NIGHTWALKER4));
        assertTrue(ItemConstants.canEquipSecondaryWeapon(1352975, Job.THUNDERBREAKER4));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352206, Job.SHADOWER));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352975, Job.HERO));
        assertFalse(ItemConstants.canEquipSecondaryWeapon(1352406, Job.BISHOP));
    }

    @Test
    void modernAccessoriesUseIndependentLegacyCompatibleSlots() {
        assertEquals(54, BodyPart.ROBOT_HEART.getValue());
        assertEquals(55, BodyPart.BADGE.getValue());
        assertEquals(56, BodyPart.EMBLEM.getValue());
        assertEquals(54, ItemConstants.getEquipSlotType(1672000));
        assertEquals(55, ItemConstants.getEquipSlotType(1182000));
        assertEquals(56, ItemConstants.getEquipSlotType(1190000));
        assertTrue(EquipSlot.ROBOT_HEART.isAllowed(-54, false));
        assertTrue(EquipSlot.BADGE.isAllowed(-55, false));
        assertTrue(EquipSlot.EMBLEM.isAllowed(-56, false));
        assertFalse(EquipSlot.ROBOT_HEART.isAllowed(-18, false));
        assertFalse(EquipSlot.EMBLEM.isAllowed(-10, false));
        assertEquals(EquipType.ROBOT_HEART, EquipType.getEquipTypeById(1672000));
        assertEquals(EquipType.BADGE, EquipType.getEquipTypeById(1182000));
        assertEquals(EquipType.EMBLEM, EquipType.getEquipTypeById(1190000));
    }

    @Test
    void legacyShoulderPositionMigratesWhenAnEquippedInventoryIsLoaded() {
        Inventory equipped = new Inventory(null, InventoryType.EQUIPPED, (byte) 96);
        Item shoulder = new Item(1152081, (short) -51, (short) 1);

        equipped.addItemFromDB(shoulder);

        assertEquals(-20, shoulder.getPosition());
        assertEquals(shoulder, equipped.getItem((short) -20));
    }

    @Test
    void legacySecondaryWeaponPositionsMigrateAwayFromTheShieldSlot() {
        Inventory equipped = new Inventory(null, InventoryType.EQUIPPED, (byte) 96);
        Item katara = new Item(1342000, (short) -BodyPart.SHIELD.getValue(), (short) 1);

        equipped.addItemFromDB(katara);

        assertEquals(-51, katara.getPosition());
        assertEquals(katara, equipped.getItem((short) -51));

        Inventory secondaryInventory = new Inventory(null, InventoryType.EQUIPPED, (byte) 96);
        Item secondary = new Item(1352206, (short) -BodyPart.SHIELD.getValue(), (short) 1);
        secondaryInventory.addItemFromDB(secondary);
        assertEquals(-51, secondary.getPosition());
        assertEquals(secondary, secondaryInventory.getItem((short) -51));
    }

    @Test
    void legacyBadgeAndEmblemPositionsMigrateToTheirIndependentSlots() {
        Inventory badgeInventory = new Inventory(null, InventoryType.EQUIPPED, (byte) 96);
        Item badge = new Item(1182000, (short) -56, (short) 1);
        badgeInventory.addItemFromDB(badge);
        assertEquals(-55, badge.getPosition());
        assertEquals(badge, badgeInventory.getItem((short) -55));

        Inventory emblemInventory = new Inventory(null, InventoryType.EQUIPPED, (byte) 96);
        Item emblem = new Item(1190000, (short) -10, (short) 1);
        emblemInventory.addItemFromDB(emblem);
        assertEquals(-56, emblem.getPosition());
        assertEquals(emblem, emblemInventory.getItem((short) -56));
    }
}
