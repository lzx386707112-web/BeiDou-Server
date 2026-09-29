package org.gms.server;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Runtime snapshot of administrator-defined set-tier bonus overrides. */
public final class SetItemBonusOverrides {
    public static final int REMOVED_VALUE = Integer.MIN_VALUE;
    private static volatile State state = new State(Collections.emptyMap(), List.of(), Set.of(), Map.of());

    private record State(Map<String, Map<String, Integer>> bonuses,
                         List<SetItemManager.Definition> customDefinitions,
                         Set<Integer> disabledBuiltInIds,
                         Map<Integer, List<List<Integer>>> slotOverrides) {
    }

    private SetItemBonusOverrides() {
    }

    public static String key(int definitionId, int requiredCount) {
        return definitionId + ":" + requiredCount;
    }

    public static Map<String, Map<String, Integer>> snapshot() {
        return state.bonuses();
    }

    public static List<SetItemManager.Definition> customDefinitions() {
        return state.customDefinitions();
    }

    public static Set<Integer> disabledBuiltInIds() {
        return state.disabledBuiltInIds();
    }

    public static Map<Integer, List<List<Integer>>> slotOverrides() {
        return state.slotOverrides();
    }

    public static synchronized void replace(Map<String, Map<String, Integer>> replacements) {
        State current = state;
        replaceAll(replacements, current.customDefinitions(), current.disabledBuiltInIds());
    }

    public static synchronized void replaceAll(
            Map<String, Map<String, Integer>> replacements,
            List<SetItemManager.Definition> customDefinitions,
            Set<Integer> disabledBuiltInIds) {
        replaceAll(replacements, customDefinitions, disabledBuiltInIds, state.slotOverrides());
    }

    public static synchronized void replaceAll(
            Map<String, Map<String, Integer>> replacements,
            List<SetItemManager.Definition> customDefinitions,
            Set<Integer> disabledBuiltInIds,
            Map<Integer, List<List<Integer>>> slotOverrides) {
        Map<String, Map<String, Integer>> copy = new LinkedHashMap<>();
        if (replacements != null) {
            replacements.forEach((key, stats) -> {
                if (key != null && stats != null) {
                    copy.put(key, Collections.unmodifiableMap(new LinkedHashMap<>(stats)));
                }
            });
        }
        List<SetItemManager.Definition> definitions = customDefinitions == null
                ? List.of() : List.copyOf(customDefinitions);
        Set<Integer> disabled = disabledBuiltInIds == null
                ? Set.of() : Collections.unmodifiableSet(new LinkedHashSet<>(disabledBuiltInIds));
        Map<Integer, List<List<Integer>>> slots = new LinkedHashMap<>();
        if (slotOverrides != null) {
            slotOverrides.forEach((id, value) -> slots.put(id,
                    value.stream().map(List::copyOf).toList()));
        }
        state = new State(Collections.unmodifiableMap(copy), definitions, disabled,
                Collections.unmodifiableMap(slots));
    }
}
