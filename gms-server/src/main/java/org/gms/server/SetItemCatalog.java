package org.gms.server;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.TypeReference;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/** Reviewed series defaults shared by combat and the admin catalog. */
public final class SetItemCatalog {
    public record Series(int id, int jobIndex, String name, List<List<Integer>> slots,
                         List<SetItemManager.Tier> tiers) { }

    private static final List<Series> SERIES = read();

    private SetItemCatalog() { }

    private static final class EquipmentNames {
        private static final java.util.Map<Integer, String> BY_ID = readNames();

        private static java.util.Map<Integer, String> readNames() {
            try (var input = SetItemCatalog.class.getResourceAsStream("/equipment-catalog/catalog.json")) {
                if (input == null) throw new IllegalStateException("Missing equipment name catalog");
                var names = new java.util.HashMap<Integer, String>();
                for (Object value : JSON.parseObject(input.readAllBytes()).getJSONArray("items")) {
                    var item = (com.alibaba.fastjson2.JSONObject) value;
                    names.put(item.getIntValue("id"), item.getString("name"));
                }
                return java.util.Map.copyOf(names);
            } catch (IOException exception) {
                throw new IllegalStateException("Cannot read equipment name catalog", exception);
            }
        }
    }

    public static String itemName(int itemId, String wzName) {
        if (wzName != null && !wzName.isBlank() && !wzName.equals(Integer.toString(itemId))) return wzName;
        return EquipmentNames.BY_ID.getOrDefault(itemId, Integer.toString(itemId));
    }

    private static List<Series> read() {
        try (var input = SetItemCatalog.class.getResourceAsStream("/set-item/catalog.json")) {
            if (input == null) throw new IllegalStateException("Missing runtime set catalog");
            return JSON.parseObject(input.readAllBytes(), new TypeReference<List<Series>>() { }.getType());
        } catch (IOException exception) {
            throw new IllegalStateException("Cannot read runtime set catalog", exception);
        }
    }

    static List<SetItemManager.Definition> apply(List<SetItemManager.Definition> legacy) {
        List<SetItemManager.Definition> result = new ArrayList<>();
        Set<Integer> covered = new java.util.HashSet<>();
        for (var definition : legacy) {
            // Match armor, never weapons shared by unrelated armor series.
            Set<Integer> armor = definition.slots().stream().flatMap(List::stream)
                    .filter(id -> id < 1300000).collect(Collectors.toSet());
            List<Series> matches = SERIES.stream().filter(series -> series.slots().stream()
                    .flatMap(List::stream).anyMatch(armor::contains)).toList();
            if (matches.size() > 1) throw new IllegalStateException("Ambiguous legacy set " + definition.id());
            if (matches.isEmpty()) {
                result.add(definition);
            } else {
                Series series = matches.getFirst();
                result.add(definition(series, definition.id(), definition.jobIndex()));
                covered.add(series.id());
            }
        }
        for (Series series : SERIES) {
            if (!covered.contains(series.id())) result.add(definition(series, series.id(), job(series.name())));
        }
        return List.copyOf(result);
    }

    private static int job(String name) {
        if (name.equals("麦克斯班·雷昂") || name.equals("维克特班·雷昂")) return 0;
        if (name.startsWith("高贵")) return switch (name) {
            case "高贵战士" -> 0;
            case "高贵流丹维奇" -> 1;
            case "高贵游侠" -> 2;
            case "高贵刺客" -> 3;
            default -> 4;
        };
        for (var suffix : List.of("战士", "战斗", "骑士")) if (name.endsWith(suffix)) return 0;
        for (var suffix : List.of("法师", "魔法师")) if (name.endsWith(suffix)) return 1;
        for (var suffix : List.of("弓箭手", "哨兵", "弓手")) if (name.endsWith(suffix)) return 2;
        for (var suffix : List.of("飞侠", "追踪者")) if (name.endsWith(suffix)) return 3;
        for (var suffix : List.of("海盗", "船长")) if (name.endsWith(suffix)) return 4;
        return -1;
    }

    private static SetItemManager.Definition definition(Series series, int id, int job) {
        List<List<Integer>> slots = series.slots().stream().map(List::copyOf).toList();
        List<SetItemManager.Tier> tiers = series.tiers().stream().map(tier ->
                new SetItemManager.Tier(tier.requiredCount(), Collections.unmodifiableMap(
                        new LinkedHashMap<>(tier.stats())))).toList();
        return new SetItemManager.Definition(id, job, series.name(), slots, tiers,
                "各档效果累计。同一槽位的候选装备只计一件。");
    }
}
