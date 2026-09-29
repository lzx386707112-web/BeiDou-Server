package org.gms.service;

import com.alibaba.fastjson2.JSON;
import org.gms.config.GameConfig;
import org.gms.dao.entity.GameConfigDO;
import org.gms.dao.mapper.GameConfigMapper;
import org.gms.exception.BizException;
import org.gms.manager.ServerManager;
import org.gms.model.dto.SetItemCatalogStorageDTO;
import org.gms.model.dto.SetItemUpdateDTO;
import org.gms.net.server.Server;
import org.gms.property.ServiceProperty;
import org.gms.server.ItemInformationProvider;
import org.gms.server.SetItemBonusOverrides;
import org.gms.server.SetItemManager;
import org.gms.provider.DataProviderFactory;
import org.gms.provider.DataProvider;
import org.gms.provider.wz.WZFiles;
import org.gms.util.DatabaseConnection;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.sql.Connection;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SetItemConfigServiceTest {
    @BeforeAll
    static void context() throws Exception {
        ApplicationContext context = mock(ApplicationContext.class, RETURNS_MOCKS);
        ServiceProperty property = new ServiceProperty();
        property.setLanguage("zh-CN");
        MessageSource messages = mock(MessageSource.class);
        when(messages.getMessage(anyString(), any(Object[].class), any(Locale.class))).thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(property);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messages);
        ConfigService configService = mock(ConfigService.class);
        when(configService.loadGameConfigs()).thenReturn(List.of());
        when(context.getBean(ConfigService.class)).thenReturn(configService);
        new ServerManager().setApplicationContext(context);
        Class.forName(GameConfig.class.getName());
        // Prevent the legacy eager singleton from opening a database or reading WZ data.
        Connection connection = mock(Connection.class, RETURNS_DEEP_STUBS);
        DataProvider provider = mock(DataProvider.class, RETURNS_MOCKS);
        try (var db = mockStatic(DatabaseConnection.class);
             var providers = mockStatic(DataProviderFactory.class)) {
            db.when(DatabaseConnection::getConnection).thenReturn(connection);
            providers.when(() -> DataProviderFactory.getDataProvider(any(WZFiles.class))).thenReturn(provider);
            Class.forName(ItemInformationProvider.class.getName());
        }
    }

    @AfterEach
    void clear() {
        SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of());
    }

    private SetItemUpdateDTO request(SetItemManager.Definition definition) {
        SetItemUpdateDTO request = new SetItemUpdateDTO();
        Map<Integer, Map<String, Integer>> tiers = new LinkedHashMap<>();
        definition.tiers().forEach(tier -> tiers.put(tier.requiredCount(), new LinkedHashMap<>(tier.stats())));
        request.setTiers(tiers);
        return request;
    }

    @Test
    void editingSlotsAndPercentagesPersistsReloadsAndResetsTogether() {
        GameConfigMapper mapper = mock(GameConfigMapper.class);
        SetItemConfigService service = new SetItemConfigService(mapper, mock(EquipmentCatalogService.class));
        var definition = SetItemManager.builtInDefinitions().getFirst();
        SetItemUpdateDTO request = request(definition);
        request.getTiers().values().forEach(stats -> stats.put("HPPct", 20));
        List<List<Integer>> slots = new ArrayList<>(definition.slots());
        slots.set(0, List.of(1002000));
        request.setSlots(slots);
        var bonuses = GameConfigDO.builder().configCode(SetItemConfigService.CONFIG_CODE).configValue("{}").build();
        var catalog = GameConfigDO.builder().configCode(SetItemConfigService.CATALOG_CONFIG_CODE).configValue("{}").build();
        when(mapper.selectOneByQuery(any())).thenReturn(bonuses, catalog);
        ItemInformationProvider items = mock(ItemInformationProvider.class);
        when(items.getName(anyInt())).thenReturn("equipment");
        when(items.itemDataExists(anyInt())).thenReturn(true);
        Server server = mock(Server.class);
        when(server.getWorlds()).thenReturn(List.of());
        try (var itemStatic = mockStatic(ItemInformationProvider.class);
             var serverStatic = mockStatic(Server.class);
             var configStatic = mockStatic(GameConfig.class)) {
            itemStatic.when(ItemInformationProvider::getInstance).thenReturn(items);
            serverStatic.when(Server::getInstance).thenReturn(server);
            assertEquals(0, service.update(definition.id(), request));
            assertEquals(slots, SetItemBonusOverrides.slotOverrides().get(definition.id()));
            assertEquals(20, SetItemManager.catalogDefinitions().getFirst().tiers().getFirst().stats().get("HPPct"));
            SetItemCatalogStorageDTO stored = JSON.parseObject(catalog.getConfigValue(), SetItemCatalogStorageDTO.class);
            assertEquals(slots, stored.getSlotOverrides().get(definition.id()));
            SetItemBonusOverrides.replaceAll(Map.of(), List.of(), Set.of(), Map.of());
            when(mapper.selectOneByQuery(any())).thenReturn(catalog, bonuses);
            service.reload();
            assertEquals(slots, SetItemManager.catalogDefinitions().getFirst().slots());
            assertEquals(20, SetItemManager.catalogDefinitions().getFirst().tiers().getFirst().stats().get("HPPct"));
            assertTrue(service.catalog().getFirst().slotsCustomized());
            when(mapper.selectOneByQuery(any())).thenReturn(bonuses, catalog);
            service.reset(definition.id());
            assertTrue(SetItemBonusOverrides.slotOverrides().isEmpty());
            assertTrue(SetItemBonusOverrides.snapshot().isEmpty());
            assertEquals(definition.slots(), SetItemManager.catalogDefinitions().getFirst().slots());
        }
    }

    @Test
    void nativeCatalogCapacityIsCheckedBeforeCreatingOrEnabling() {
        GameConfigMapper mapper = mock(GameConfigMapper.class);
        SetItemConfigService service = new SetItemConfigService(mapper, mock(EquipmentCatalogService.class));
        int disabledId = SetItemManager.builtInDefinitions().getFirst().id();
        List<SetItemManager.Definition> custom = java.util.stream.IntStream
                .range(0, 97 - SetItemManager.builtInDefinitions().size())
                .mapToObj(index -> new SetItemManager.Definition(20000 + index, -1, "test",
                        List.of(List.of(1002000)), List.of(new SetItemManager.Tier(1, Map.of("PDD", 1))), "test"))
                .toList();
        SetItemBonusOverrides.replaceAll(Map.of(), custom, Set.of(disabledId), Map.of());
        assertEquals(96, SetItemManager.definitions().size());
        assertTrue(assertThrows(BizException.class, () -> service.create(null)).getMessage().contains("96"));
        assertTrue(assertThrows(BizException.class,
                () -> service.setBuiltInEnabled(disabledId, true)).getMessage().contains("96"));
        verifyNoInteractions(mapper);
    }

    @Test
    void invalidSlotEditsAndRatesDoNotWriteConfig() {
        GameConfigMapper mapper = mock(GameConfigMapper.class);
        SetItemConfigService service = new SetItemConfigService(mapper, mock(EquipmentCatalogService.class));
        var definition = SetItemManager.builtInDefinitions().getFirst();
        SetItemUpdateDTO request = request(definition);
        for (List<List<Integer>> invalid : List.of(List.<List<Integer>>of(),
                List.of(List.<Integer>of()), List.of(List.of(1002000, 1002000)),
                List.of(List.of(2000000)))) {
            request.setSlots(invalid);
            assertThrows(BizException.class, () -> service.update(definition.id(), request));
        }
        request.setSlots(null);
        request.getTiers().values().forEach(stats -> stats.put("HPPct", 10001));
        assertThrows(BizException.class, () -> service.update(definition.id(), request));
        request.getTiers().values().forEach(stats -> {
            stats.clear();
            SetItemManager.SUPPORTED_STAT_KEYS.forEach(key -> stats.put(key, 1));
        });
        assertThrows(BizException.class, () -> service.update(definition.id(), request));
        verifyNoInteractions(mapper);
    }
}
