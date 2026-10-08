package org.gms.util;

import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Inventory;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.net.packet.Packet;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.server.SetItemManager;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SetItemPacketTest {
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
    void destinyStaffPacketMatchesClientDecoderContract() {
        Job bishop = Job.BISHOP;
        Character character = mock(Character.class);
        Inventory equipped = new Inventory(character, InventoryType.EQUIPPED, (byte) 96);
        equipped.addItemFromDB(new Item(1382289, (short) -11, (short) 1));
        when(character.getJob()).thenReturn(bishop);
        when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(equipped);

        Packet packet = PacketCreator.setItemUpdate(SetItemManager.compute(character), Integer::toString);
        assertTrue(packet.getBytes().length <= 0xFFFF);
        ByteBuffer data = ByteBuffer.wrap(packet.getBytes()).order(ByteOrder.LITTLE_ENDIAN);
        assertEquals(0x17A, read2(data));
        int setCount = read2(data);
        assertTrue(setCount >= SetItemManager.compute(character).panels().stream()
                .filter(SetItemManager.Panel::jobEligible).count());
        assertTrue(setCount <= 96);

        for (int set = 0; set < setCount; set++) {
            int setId = data.getInt();
            if (set == 0) {
                assertEquals(10086, setId);
            }
            readString(data);
            read2(data);
            int slotCount = read2(data);
            for (int slot = 0; slot < slotCount; slot++) {
                int altCount = read2(data);
                for (int alt = 0; alt < altCount; alt++) {
                    data.getInt();
                    data.get();
                    readString(data);
                    readString(data);
                    data.getInt();
                }
            }
            int tierCount = read2(data);
            for (int tier = 0; tier < tierCount; tier++) {
                read2(data);
                int statCount = read2(data);
                assertTrue(statCount > 0 && statCount <= SetItemManager.STAT_KEYS.length);
                for (int stat = 0; stat < statCount; stat++) {
                    readString(data);
                    assertNotEquals(0, data.getInt());
                }
            }
            read2(data);
            readString(data);
            data.getInt();
            data.getInt();
        }
        assertEquals(0, read2(data));
        assertEquals(0, data.remaining());
    }

    @Test
    void unequippedItemsInEverySlotAndAlternativeRemainHoverLookupKeys() throws java.io.IOException {
        Map<Integer, String> names = new HashMap<>();
        try (var input = getClass().getResourceAsStream("/equipment-catalog/catalog.json")) {
            var items = com.alibaba.fastjson2.JSON.parseObject(input.readAllBytes()).getJSONArray("items");
            items.forEach(value -> {
                var item = (com.alibaba.fastjson2.JSONObject) value;
                names.put(item.getIntValue("id"), item.getString("name"));
            });
        }
        for (Job job : List.of(Job.HERO, Job.BISHOP, Job.BOWMASTER, Job.NIGHTLORD, Job.CORSAIR)) {
            Character character = mock(Character.class);
            when(character.getJob()).thenReturn(job);
            when(character.getInventory(InventoryType.EQUIPPED)).thenReturn(
                    new Inventory(character, InventoryType.EQUIPPED, (byte) 96));
            var result = SetItemManager.compute(character);
            Map<Integer, SetItemManager.Panel> expected = new HashMap<>();
            result.panels().stream().filter(SetItemManager.Panel::jobEligible)
                    .forEach(panel -> expected.put(panel.definition().id(), panel));
            // Reproduce a deployment without modern String XML: use packaged names.
            byte[] bytes = PacketCreator.setItemUpdate(result, id -> null).getBytes();
            assertTrue(bytes.length <= 60_000);
            ByteBuffer data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
            assertEquals(0x17A, read2(data));
            int count = read2(data);
            assertTrue(count <= 96);
            Map<Integer, Set<Integer>> visible = new HashMap<>();
            for (int view = 0; view < count; view++) {
                int id = data.getInt();
                var panel = expected.get(id);
                readString(data);
                assertEquals(panel.definition().completeCount(), read2(data));
                int slots = read2(data);
                assertTrue(slots <= 8);
                Set<Integer> items = visible.computeIfAbsent(id, ignored -> new HashSet<>());
                for (int slot = 0; slot < slots; slot++) {
                    int alternatives = read2(data);
                    assertTrue(alternatives <= 10);
                    for (int alt = 0; alt < alternatives; alt++) {
                        int itemId = data.getInt();
                        items.add(itemId);
                        assertEquals(0, data.get());
                        assertEquals(names.get(itemId), readText(data));
                        readString(data);
                        int originalSlot = data.getInt();
                        assertTrue(originalSlot > 0 && originalSlot <= panel.definition().slots().size());
                        assertTrue(panel.definition().slots().get(originalSlot - 1).contains(itemId));
                    }
                }
                int tiers = read2(data);
                for (int tier = 0; tier < tiers; tier++) {
                    read2(data);
                    int stats = read2(data);
                    for (int stat = 0; stat < stats; stat++) {
                        readString(data);
                        data.getInt();
                    }
                }
                assertEquals(0xffff, read2(data));
                readString(data);
                assertEquals(0, data.getInt());
                assertEquals(0, data.getInt());
            }
            assertEquals(0, read2(data));
            assertEquals(0, data.remaining());
            expected.forEach((id, panel) -> {
                Set<Integer> items = new HashSet<>();
                panel.definition().slots().forEach(items::addAll);
                assertEquals(items, visible.get(id), job + " set " + id);
            });
            assertTrue(visible.values().stream().anyMatch(ids -> ids.contains(1302258)),
                    "Ultimate weapon in slot 11 must be visible without equipping it");
            String fixtureDirectory = System.getProperty("setItemPacketFixtureDirectory");
            if (fixtureDirectory != null) {
                java.nio.file.Path directory = java.nio.file.Path.of(fixtureDirectory);
                java.nio.file.Files.createDirectories(directory);
                java.nio.file.Files.write(directory.resolve(job.name() + ".packet"), bytes);
            }
        }
    }

    private static int read2(ByteBuffer data) {
        return Short.toUnsignedInt(data.getShort());
    }

    private static void readString(ByteBuffer data) {
        int length = read2(data);
        data.position(data.position() + length);
    }

    private static String readText(ByteBuffer data) {
        byte[] bytes = new byte[read2(data)];
        data.get(bytes);
        return new String(bytes, java.nio.charset.Charset.forName("GBK"));
    }

    @Test
    void missingAndNumericWzNamesFallBackToPackagedEquipmentNames() {
        assertEquals("终极腰带", org.gms.server.SetItemCatalog.itemName(1132209, null));
        assertEquals("终极肩章", org.gms.server.SetItemCatalog.itemName(1152119, "1152119"));
        assertEquals("终极战剑", org.gms.server.SetItemCatalog.itemName(1302258, ""));
        assertEquals("自定义名称", org.gms.server.SetItemCatalog.itemName(1302258, "自定义名称"));
    }
}
