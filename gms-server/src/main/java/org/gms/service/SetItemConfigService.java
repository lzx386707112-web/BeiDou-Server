package org.gms.service;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.TypeReference;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.gms.client.Character;
import org.gms.client.inventory.InventoryType;
import org.gms.config.GameConfig;
import org.gms.constants.inventory.ItemConstants;
import org.gms.dao.entity.GameConfigDO;
import org.gms.dao.mapper.GameConfigMapper;
import org.gms.exception.BizException;
import org.gms.model.dto.SetItemCatalogStorageDTO;
import org.gms.model.dto.SetItemConfigDTO;
import org.gms.model.dto.SetItemDefinitionCreateDTO;
import org.gms.model.dto.SetItemEquipmentDTO;
import org.gms.model.dto.SetItemUpdateDTO;
import org.gms.net.server.Server;
import org.gms.server.ItemInformationProvider;
import org.gms.server.SetItemBonusOverrides;
import org.gms.server.SetItemManager;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import static org.gms.dao.entity.table.GameConfigDOTableDef.GAME_CONFIG_D_O;

@Service
@RequiredArgsConstructor
@Slf4j
public class SetItemConfigService {
    public static final String CONFIG_CODE = "set_item_bonus_overrides";
    public static final String CATALOG_CONFIG_CODE = "set_item_catalog_customizations";
    private static final String CONFIG_TYPE = "server";
    private static final String CONFIG_SUB_TYPE = "Set Items";
    private static final int FIRST_CUSTOM_DEFINITION_ID = 20_000;
    private static final int MAX_ACTIVE_DEFINITIONS = 96;
    private static final int MAX_SLOTS = 8;
    private static final int MAX_ITEMS_PER_SLOT = 10;
    private static final int MAX_TIER_STATS = 24;
    private static final int MAX_NAME_LENGTH = 64;
    private static final int MAX_FLAT_VALUE = 1_000_000;
    private static final int MAX_RATE_VALUE = 10_000;

    private final GameConfigMapper gameConfigMapper;
    private final EquipmentCatalogService equipmentCatalogService;

    @PostConstruct
    public synchronized void reload() {
        CatalogState catalogState = parseCatalog(valueOf(CATALOG_CONFIG_CODE));
        List<SetItemManager.Definition> baseDefinitions = new ArrayList<>(
                SetItemManager.builtInDefinitions());
        baseDefinitions.addAll(catalogState.customDefinitions());
        Map<String, Map<String, Integer>> bonuses = parseBonuses(
                valueOf(CONFIG_CODE), baseDefinitions);
        SetItemBonusOverrides.replaceAll(bonuses, catalogState.customDefinitions(),
                catalogState.disabledBuiltInIds(), catalogState.slotOverrides());
    }

    public int reloadAndRefresh() {
        reload();
        return refreshOnlineCharacters();
    }

    public List<SetItemConfigDTO> catalog() {
        Map<Integer, SetItemManager.Definition> defaults = new LinkedHashMap<>();
        SetItemManager.defaultDefinitions().forEach(definition -> defaults.put(definition.id(), definition));
        Map<String, Map<String, Integer>> overrides = SetItemBonusOverrides.snapshot();
        List<SetItemConfigDTO> result = new ArrayList<>();
        ItemInformationProvider itemInformation = ItemInformationProvider.getInstance();
        for (SetItemManager.Definition definition : SetItemManager.catalogDefinitions()) {
            SetItemManager.Definition base = defaults.get(definition.id());
            List<List<SetItemEquipmentDTO>> slots = definition.slots().stream()
                    .map(slot -> slot.stream()
                            .map(itemId -> new SetItemEquipmentDTO(itemId,
                                    itemName(itemInformation, itemId)))
                            .toList())
                    .toList();
            List<SetItemConfigDTO.Tier> tiers = new ArrayList<>();
            for (int index = 0; index < definition.tiers().size(); index++) {
                SetItemManager.Tier tier = definition.tiers().get(index);
                SetItemManager.Tier defaultTier = base.tiers().get(index);
                tiers.add(new SetItemConfigDTO.Tier(
                        tier.requiredCount(), tier.stats(), defaultTier.stats(),
                        overrides.containsKey(SetItemBonusOverrides.key(
                                definition.id(), tier.requiredCount()))));
            }
            result.add(new SetItemConfigDTO(definition.id(), definition.jobIndex(),
                    definition.name(), definition.completeCount(),
                    SetItemManager.isBuiltIn(definition.id()),
                    SetItemManager.isEnabled(definition.id()), slots, List.copyOf(tiers),
                    base.slots().stream().map(slot -> slot.stream()
                            .map(itemId -> new SetItemEquipmentDTO(itemId,
                                    itemName(itemInformation, itemId))).toList()).toList(),
                    SetItemBonusOverrides.slotOverrides().containsKey(definition.id())));
        }
        return List.copyOf(result);
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int create(SetItemDefinitionCreateDTO request) {
        validateCatalogCapacity();
        int definitionId = nextCustomDefinitionId();
        SetItemManager.Definition definition = buildDefinition(request, definitionId, true);
        List<SetItemManager.Definition> customDefinitions = new ArrayList<>(
                SetItemBonusOverrides.customDefinitions());
        customDefinitions.add(definition);
        persistCatalog(customDefinitions, SetItemBonusOverrides.disabledBuiltInIds());
        refreshOnlineCharacters();
        return definitionId;
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int setBuiltInEnabled(int definitionId, boolean enabled) {
        if (!SetItemManager.isBuiltIn(definitionId)) {
            throw BizException.illegalArgument("只有内置套装可以停用或恢复");
        }
        if (enabled && !SetItemManager.isEnabled(definitionId)) {
            validateCatalogCapacity();
        }
        Set<Integer> disabled = new LinkedHashSet<>(
                SetItemBonusOverrides.disabledBuiltInIds());
        if (enabled) {
            disabled.remove(definitionId);
        } else {
            disabled.add(definitionId);
        }
        persistCatalog(SetItemBonusOverrides.customDefinitions(), disabled);
        return refreshOnlineCharacters();
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int deleteCustom(int definitionId) {
        if (SetItemManager.isBuiltIn(definitionId)) {
            throw BizException.illegalArgument("内置套装不能删除，只能停用");
        }
        List<SetItemManager.Definition> customDefinitions = new ArrayList<>(
                SetItemBonusOverrides.customDefinitions());
        boolean removed = customDefinitions.removeIf(
                definition -> definition.id() == definitionId);
        if (!removed) {
            throw BizException.illegalArgument("自定义套装不存在: " + definitionId);
        }
        Map<String, Map<String, Integer>> bonuses = mutableSnapshot();
        removeDefinitionOverrides(bonuses, definitionId);
        Map<Integer, List<List<Integer>>> slots = new LinkedHashMap<>(
                SetItemBonusOverrides.slotOverrides());
        slots.remove(definitionId);
        saveConfig(CONFIG_CODE, JSON.toJSONString(bonuses));
        saveConfig(CATALOG_CONFIG_CODE, serializeCatalog(customDefinitions,
                SetItemBonusOverrides.disabledBuiltInIds(), slots));
        SetItemBonusOverrides.replaceAll(bonuses, customDefinitions,
                SetItemBonusOverrides.disabledBuiltInIds(), slots);
        return refreshOnlineCharacters();
    }

    public List<SetItemEquipmentDTO> searchEquipment(String keyword) {
        return equipmentCatalogService.searchSimple(keyword);
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int update(int definitionId, SetItemUpdateDTO request) {
        SetItemManager.Definition definition = requireDefinition(definitionId);
        if (request == null || request.getTiers() == null) {
            throw BizException.illegalArgument("套装档位配置不能为空");
        }
        Set<Integer> requiredCounts = definition.tiers().stream()
                .map(SetItemManager.Tier::requiredCount)
                .collect(java.util.stream.Collectors.toSet());
        if (!request.getTiers().keySet().equals(requiredCounts)) {
            throw BizException.illegalArgument("套装档位不完整或包含未知档位");
        }
        Map<Integer, List<List<Integer>>> slots = new LinkedHashMap<>(
                SetItemBonusOverrides.slotOverrides());
        if (request.getSlots() != null) {
            List<List<Integer>> validated = validateSlots(request.getSlots(), true);
            validateTierSlots(definition, validated);
            if (validated.equals(definition.slots())) {
                slots.remove(definitionId);
            } else {
                slots.put(definitionId, validated);
            }
        }
        Map<String, Map<String, Integer>> updated = mutableSnapshot();
        removeDefinitionOverrides(updated, definitionId);
        for (SetItemManager.Tier tier : definition.tiers()) {
            Map<String, Integer> values = request.getTiers().get(tier.requiredCount());
            if (values == null) {
                throw BizException.illegalArgument("套装档位属性不能为空");
            }
            if (values.size() > MAX_TIER_STATS) {
                throw BizException.illegalArgument("每档最多支持 " + MAX_TIER_STATS + " 项属性");
            }
            Map<String, Integer> differences = new LinkedHashMap<>();
            for (Map.Entry<String, Integer> stat : values.entrySet()) {
                if (!SetItemManager.SUPPORTED_STAT_KEYS.contains(stat.getKey())) {
                    throw BizException.illegalArgument("不支持的套装属性: " + stat.getKey());
                }
                Integer value = values.get(stat.getKey());
                validateValue(stat.getKey(), value);
                if (!value.equals(tier.stats().get(stat.getKey()))) {
                    differences.put(stat.getKey(), value);
                }
            }
            for (String defaultStat : tier.stats().keySet()) {
                if (!values.containsKey(defaultStat)) {
                    differences.put(defaultStat, SetItemBonusOverrides.REMOVED_VALUE);
                }
            }
            if (!differences.isEmpty()) {
                updated.put(SetItemBonusOverrides.key(definitionId, tier.requiredCount()), differences);
            }
        }
        persistConfiguration(updated, slots);
        return refreshOnlineCharacters();
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int reset(int definitionId) {
        requireDefinition(definitionId);
        Map<String, Map<String, Integer>> updated = mutableSnapshot();
        removeDefinitionOverrides(updated, definitionId);
        Map<Integer, List<List<Integer>>> slots = new LinkedHashMap<>(
                SetItemBonusOverrides.slotOverrides());
        slots.remove(definitionId);
        persistConfiguration(updated, slots);
        return refreshOnlineCharacters();
    }

    private SetItemManager.Definition requireDefinition(int definitionId) {
        return SetItemManager.defaultDefinitions().stream()
                .filter(definition -> definition.id() == definitionId)
                .findFirst()
                .orElseThrow(() -> BizException.illegalArgument("套装不存在: " + definitionId));
    }

    private void validateCatalogCapacity() {
        if (SetItemManager.definitions().size() >= MAX_ACTIVE_DEFINITIONS) {
            throw BizException.illegalArgument("客户端最多支持 " + MAX_ACTIVE_DEFINITIONS + " 套启用套装");
        }
    }

    private void validateValue(String stat, Integer value) {
        int maximum = isRate(stat) ? MAX_RATE_VALUE : MAX_FLAT_VALUE;
        if (value == null || value < 0 || value > maximum) {
            throw BizException.illegalArgument(stat + " 必须在 0 到 " + maximum + " 之间");
        }
    }

    private boolean isRate(String stat) {
        String normalized = stat.toLowerCase(Locale.ROOT);
        return normalized.endsWith("rate") || normalized.endsWith("pct")
                || normalized.equals("finaldamage") || normalized.equals("bossdamage")
                || normalized.equals("statusres") || normalized.equals("buffduration");
    }

    private Map<String, Map<String, Integer>> mutableSnapshot() {
        Map<String, Map<String, Integer>> copy = new LinkedHashMap<>();
        SetItemBonusOverrides.snapshot().forEach(
                (key, stats) -> copy.put(key, new LinkedHashMap<>(stats)));
        return copy;
    }

    private void removeDefinitionOverrides(Map<String, Map<String, Integer>> values,
                                           int definitionId) {
        String prefix = definitionId + ":";
        values.keySet().removeIf(key -> key.startsWith(prefix));
    }

    private Map<String, Map<String, Integer>> parseBonuses(
            String json, List<SetItemManager.Definition> definitions) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            Map<String, Map<String, Integer>> parsed = JSON.parseObject(
                    json, new TypeReference<LinkedHashMap<String, Map<String, Integer>>>() { });
            return sanitizeBonuses(parsed, definitions);
        } catch (RuntimeException exception) {
            log.error("Invalid set item bonus override config; using defaults", exception);
            return Map.of();
        }
    }

    private Map<String, Map<String, Integer>> sanitizeBonuses(
            Map<String, Map<String, Integer>> candidate,
            List<SetItemManager.Definition> definitions) {
        if (candidate == null || candidate.isEmpty()) {
            return Map.of();
        }
        Map<String, Map<String, Integer>> result = new LinkedHashMap<>();
        for (SetItemManager.Definition definition : definitions) {
            for (SetItemManager.Tier tier : definition.tiers()) {
                String key = SetItemBonusOverrides.key(definition.id(), tier.requiredCount());
                Map<String, Integer> source = candidate.get(key);
                if (source == null) {
                    continue;
                }
                Map<String, Integer> valid = new LinkedHashMap<>();
                for (Map.Entry<String, Integer> stat : source.entrySet()) {
                    String statName = stat.getKey();
                    Integer value = stat.getValue();
                    if (!SetItemManager.SUPPORTED_STAT_KEYS.contains(statName)) {
                        continue;
                    }
                    if (value != null && value == SetItemBonusOverrides.REMOVED_VALUE
                            && tier.stats().containsKey(statName)) {
                        valid.put(statName, value);
                        continue;
                    }
                    int maximum = isRate(statName) ? MAX_RATE_VALUE : MAX_FLAT_VALUE;
                    if (value != null && value >= 0 && value <= maximum) {
                        valid.put(statName, value);
                    }
                }
                if (!valid.isEmpty()) {
                    result.put(key, valid);
                }
            }
        }
        return result;
    }

    private CatalogState parseCatalog(String json) {
        if (json == null || json.isBlank()) {
            return new CatalogState(List.of(), Set.of(), Map.of());
        }
        try {
            SetItemCatalogStorageDTO storage = JSON.parseObject(
                    json, SetItemCatalogStorageDTO.class);
            if (storage == null) {
                return new CatalogState(List.of(), Set.of(), Map.of());
            }
            List<SetItemManager.Definition> customDefinitions = new ArrayList<>();
            Set<Integer> definitionIds = new HashSet<>();
            if (storage.getCustomDefinitions() != null) {
                for (SetItemDefinitionCreateDTO stored : storage.getCustomDefinitions()) {
                    if (stored == null || stored.getId() == null
                            || stored.getId() < FIRST_CUSTOM_DEFINITION_ID
                            || !definitionIds.add(stored.getId())) {
                        throw BizException.illegalArgument("自定义套装ID无效或重复");
                    }
                    customDefinitions.add(buildDefinition(
                            stored, stored.getId(), false));
                }
            }
            Set<Integer> disabled = new LinkedHashSet<>();
            if (storage.getDisabledBuiltInIds() != null) {
                storage.getDisabledBuiltInIds().stream()
                        .filter(SetItemManager::isBuiltIn)
                        .forEach(disabled::add);
            }
            Map<Integer, List<List<Integer>>> slots = new LinkedHashMap<>();
            List<SetItemManager.Definition> definitions = new ArrayList<>(SetItemManager.builtInDefinitions());
            definitions.addAll(customDefinitions);
            if (storage.getSlotOverrides() != null) {
                for (SetItemManager.Definition definition : definitions) {
                    List<List<Integer>> candidate = storage.getSlotOverrides().get(definition.id());
                    if (candidate == null) continue;
                    List<List<Integer>> validated = validateSlots(candidate, false);
                    validateTierSlots(definition, validated);
                    if (!validated.equals(definition.slots())) slots.put(definition.id(), validated);
                }
            }
            return new CatalogState(List.copyOf(customDefinitions),
                    Collections.unmodifiableSet(disabled), Collections.unmodifiableMap(slots));
        } catch (RuntimeException exception) {
            log.error("Invalid custom set item catalog config; using built-in catalog", exception);
            return new CatalogState(List.of(), Set.of(), Map.of());
        }
    }

    private SetItemManager.Definition buildDefinition(SetItemDefinitionCreateDTO request,
                                                      int definitionId,
                                                      boolean verifyEquipmentData) {
        if (request == null || request.getName() == null
                || request.getName().trim().isEmpty()) {
            throw BizException.illegalArgument("套装名称不能为空");
        }
        String name = request.getName().trim();
        if (name.length() > MAX_NAME_LENGTH) {
            throw BizException.illegalArgument("套装名称不能超过 " + MAX_NAME_LENGTH + " 个字符");
        }
        Integer jobIndex = request.getJobIndex();
        if (jobIndex == null || jobIndex < -1 || jobIndex > 4) {
            throw BizException.illegalArgument("适用职业必须是全职业或五大职业系之一");
        }
        List<List<Integer>> slots = validateSlots(request.getSlots(), verifyEquipmentData);
        if (request.getTiers() == null || request.getTiers().isEmpty()) {
            throw BizException.illegalArgument("至少需要一个套装效果档位");
        }
        if (verifyEquipmentData && request.getTiers().size() > 8) {
            throw BizException.illegalArgument("最多支持 8 个套装效果档位");
        }
        List<SetItemManager.Tier> tiers = new ArrayList<>();
        request.getTiers().entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> {
                    Integer requiredCount = entry.getKey();
                    Map<String, Integer> sourceStats = entry.getValue();
                    if (requiredCount == null || requiredCount < 1
                            || requiredCount > slots.size()) {
                        throw BizException.illegalArgument("套装效果件数不能超过槽位数量");
                    }
                    if (sourceStats == null || sourceStats.isEmpty()) {
                        throw BizException.illegalArgument("套装效果属性不能为空");
                    }
                    if (verifyEquipmentData && sourceStats.size() > MAX_TIER_STATS) {
                        throw BizException.illegalArgument("每档最多支持 " + MAX_TIER_STATS + " 项属性");
                    }
                    Map<String, Integer> stats = new LinkedHashMap<>();
                    for (Map.Entry<String, Integer> stat : sourceStats.entrySet()) {
                        if (!SetItemManager.SUPPORTED_STAT_KEYS.contains(stat.getKey())) {
                            throw BizException.illegalArgument("不支持的套装属性: " + stat.getKey());
                        }
                        validateValue(stat.getKey(), stat.getValue());
                        stats.put(stat.getKey(), stat.getValue());
                    }
                    tiers.add(new SetItemManager.Tier(requiredCount,
                            Collections.unmodifiableMap(stats)));
                });
        return new SetItemManager.Definition(definitionId, jobIndex, name,
                Collections.unmodifiableList(slots), List.copyOf(tiers),
                "管理后台自定义套装。套装档位效果可累计。");
    }

    private int nextCustomDefinitionId() {
        return SetItemBonusOverrides.customDefinitions().stream()
                .mapToInt(SetItemManager.Definition::id)
                .max()
                .orElse(FIRST_CUSTOM_DEFINITION_ID - 1) + 1;
    }

    private List<List<Integer>> validateSlots(List<List<Integer>> candidates,
                                               boolean verifyEquipmentData) {
        int maxSlots = verifyEquipmentData ? MAX_SLOTS : 20;
        int maxItems = verifyEquipmentData ? MAX_ITEMS_PER_SLOT : 50;
        if (candidates == null || candidates.isEmpty() || candidates.size() > maxSlots) {
            throw BizException.illegalArgument("套装槽位数量必须在 1 到 " + MAX_SLOTS + " 之间");
        }
        List<List<Integer>> slots = new ArrayList<>();
        Set<Integer> allItems = new HashSet<>();
        for (List<Integer> sourceSlot : candidates) {
            if (sourceSlot == null || sourceSlot.isEmpty() || sourceSlot.size() > maxItems) {
                throw BizException.illegalArgument("每个槽位必须包含 1 到 " + MAX_ITEMS_PER_SLOT + " 件候选装备");
            }
            for (Integer itemId : sourceSlot) {
                if (itemId == null || itemId <= 0
                        || ItemConstants.getInventoryType(itemId) != InventoryType.EQUIP) {
                    throw BizException.illegalArgument("套装槽位只能包含装备物品ID");
                }
                if (!allItems.add(itemId)) {
                    throw BizException.illegalArgument("同一件装备不能出现在多个套装槽位中: " + itemId);
                }
            }
            slots.add(List.copyOf(sourceSlot));
        }
        if (verifyEquipmentData) {
            ItemInformationProvider itemInformation = ItemInformationProvider.getInstance();
            for (Integer itemId : allItems) {
                if (itemInformation.getName(itemId) == null || !itemInformation.itemDataExists(itemId)) {
                    throw BizException.illegalArgument("装备不存在: " + itemId);
                }
            }
        }
        return List.copyOf(slots);
    }

    private void validateTierSlots(SetItemManager.Definition definition, List<List<Integer>> slots) {
        if (definition.tiers().stream().anyMatch(tier -> tier.requiredCount() > slots.size())) {
            throw BizException.illegalArgument("套装槽位数量不能少于现有效果档位所需件数");
        }
    }

    private String serializeCatalog(List<SetItemManager.Definition> customDefinitions,
                                    Set<Integer> disabledBuiltInIds) {
        return serializeCatalog(customDefinitions, disabledBuiltInIds,
                SetItemBonusOverrides.slotOverrides());
    }

    private String serializeCatalog(List<SetItemManager.Definition> customDefinitions,
                                    Set<Integer> disabledBuiltInIds,
                                    Map<Integer, List<List<Integer>>> slots) {
        SetItemCatalogStorageDTO storage = new SetItemCatalogStorageDTO();
        storage.setSlotOverrides(slots);
        storage.setDisabledBuiltInIds(new LinkedHashSet<>(disabledBuiltInIds));
        storage.setCustomDefinitions(customDefinitions.stream()
                .map(this::toStoredDefinition)
                .toList());
        return JSON.toJSONString(storage);
    }

    private SetItemDefinitionCreateDTO toStoredDefinition(
            SetItemManager.Definition definition) {
        SetItemDefinitionCreateDTO stored = new SetItemDefinitionCreateDTO();
        stored.setId(definition.id());
        stored.setName(definition.name());
        stored.setJobIndex(definition.jobIndex());
        stored.setSlots(definition.slots());
        Map<Integer, Map<String, Integer>> tiers = new LinkedHashMap<>();
        definition.tiers().forEach(tier -> tiers.put(tier.requiredCount(), tier.stats()));
        stored.setTiers(tiers);
        return stored;
    }

    private String itemName(ItemInformationProvider itemInformation, int itemId) {
        String name = itemInformation.getName(itemId);
        return name == null || name.isBlank() ? "未知装备" : name;
    }

    private String valueOf(String configCode) {
        GameConfigDO config = findConfig(configCode);
        return config == null ? null : config.getConfigValue();
    }

    private GameConfigDO findConfig(String configCode) {
        return gameConfigMapper.selectOneByQuery(QueryWrapper.create()
                .where(GAME_CONFIG_D_O.CONFIG_TYPE.eq(CONFIG_TYPE))
                .and(GAME_CONFIG_D_O.CONFIG_CODE.eq(configCode)));
    }

    private void saveConfig(String configCode, String json) {
        GameConfigDO config = findConfig(configCode);
        if (config == null) {
            config = GameConfigDO.builder()
                    .configType(CONFIG_TYPE)
                    .configSubType(CONFIG_SUB_TYPE)
                    .configClazz(String.class.getName())
                    .configCode(configCode)
                    .configValue(json)
                    .configDesc(configCode)
                    .updateTime(new Date())
                    .build();
            gameConfigMapper.insertSelective(config);
            GameConfig.add(config);
        } else {
            config.setConfigValue(json);
            config.setUpdateTime(new Date());
            gameConfigMapper.update(config);
            GameConfig.update(config);
        }
    }

    private void persistConfiguration(Map<String, Map<String, Integer>> bonuses,
                                      Map<Integer, List<List<Integer>>> slots) {
        saveConfig(CONFIG_CODE, JSON.toJSONString(bonuses));
        saveConfig(CATALOG_CONFIG_CODE, serializeCatalog(SetItemBonusOverrides.customDefinitions(),
                SetItemBonusOverrides.disabledBuiltInIds(), slots));
        SetItemBonusOverrides.replaceAll(bonuses,
                SetItemBonusOverrides.customDefinitions(),
                SetItemBonusOverrides.disabledBuiltInIds(), slots);
    }

    private void persistCatalog(List<SetItemManager.Definition> customDefinitions,
                                Set<Integer> disabledBuiltInIds) {
        saveConfig(CATALOG_CONFIG_CODE,
                serializeCatalog(customDefinitions, disabledBuiltInIds));
        SetItemBonusOverrides.replaceAll(SetItemBonusOverrides.snapshot(),
                customDefinitions, disabledBuiltInIds);
    }

    private record CatalogState(List<SetItemManager.Definition> customDefinitions,
                                Set<Integer> disabledBuiltInIds,
                                Map<Integer, List<List<Integer>>> slotOverrides) {
    }

    private int refreshOnlineCharacters() {
        int refreshed = 0;
        for (var world : Server.getInstance().getWorlds()) {
            for (Character character : world.getPlayerStorage().getAllCharacters()) {
                try {
                    character.refreshSetItemBonuses();
                    refreshed++;
                } catch (RuntimeException exception) {
                    log.warn("Failed to refresh set bonuses for character {}", character.getId(), exception);
                }
            }
        }
        return refreshed;
    }
}
