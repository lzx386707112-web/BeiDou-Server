from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
EVENT_MAPS = (
    410007100, 410007120, 410007140, 410007160,
    410007180, 410007200, 410007220, 410007240,
    410007260, 410007280, 410007300,
)
BATTLE_MAPS = (410007140, 410007180, 410007220, 410007260, 410007300)


def test_karing_expedition_type_and_transport_entry_exist():
    expedition_type = (
        ROOT / "gms-server/src/main/java/org/gms/server/expeditions/ExpeditionType.java"
    ).read_text()
    transport = (
        ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/新高级boss传送.js"
    ).read_text()
    entrance = (
        ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/咖凌终局之战.js"
    ).read_text()

    assert "KARING(1, 30, 100, 255, 5)" in expedition_type
    assert "咖凌·终局之战" in transport
    assert 'cm.openNpc(9900001, "咖凌终局之战")' in transport
    assert "ExpeditionType.KARING" in entrance
    assert 'cm.getEventManager("KaringFinalBattle")' not in entrance
    assert 'var eventName = "KaringFinalBattle"' in entrance
    assert "em.startInstance(expedition)" in entrance


def test_karing_event_owns_full_map_sequence_and_resets_entry_markers():
    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        text = (ROOT / tree / "event/KaringFinalBattle.js").read_text()
        event_map_block = re.search(r"var eventMaps = \[(.*?)\];", text, re.S)
        assert event_map_block is not None
        assert tuple(map(int, re.findall(r"\d{9}", event_map_block.group(1)))) == EVENT_MAPS
        assert "player.resetEnteredScript(eventMaps[i])" in text
        assert 'em.newInstance("KaringFinalBattle" + channel)' in text
        assert "eim.getInstanceMap(eventMaps[i])" in text
        assert "map.resetPQ(1)" in text


def test_karing_event_enforces_per_character_twenty_death_limit():
    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        text = (ROOT / tree / "event/KaringFinalBattle.js").read_text()
        for map_id in BATTLE_MAPS:
            assert f'"{map_id}"' in text
        assert 'var deathKey = "death_" + player.getId()' in text
        assert "eim.getIntProperty(deathKey) + 1" in text
        assert "if (deaths >= maxDeaths)" in text
        assert "player.respawn(eim, exitMap)" in text
        assert "player.updateHp(50)" in text
        assert "player.changeMap(eim.getMapInstance(mapId), revivePosition)" in text
        assert "revivePoint == null && !isEventMap(mapId)" in text
        assert "player.getPosition()" in text
        assert "return false" in text


def test_karing_final_boss_closes_reentry_and_stays_in_p3_map():
    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        text = (ROOT / tree / "event/KaringFinalBattle.js").read_text()
        assert "mob.getId() == 8880842" in text
        assert 'eim.setProperty("canJoin", "0")' in text
        assert "eim.setEventCleared()" in text
        assert "eim.startEventTimer(300000)" in text


def test_karing_drop_migration_contains_compatible_tms_subset():
    sql = (
        ROOT
        / "gms-server/src/main/resources/db/migration/"
        "V2.1.58__add_karing_compatible_drops.sql"
    ).read_text(encoding="utf-8")
    rows = {
        int(item_id): (int(minimum), int(maximum), int(chance))
        for item_id, minimum, maximum, chance in re.findall(
            r"\(8880842, (\d+), (\d+), (\d+), 0, (\d+)\)", sql
        )
    }
    eternal = {
        *range(1005980, 1005985),
        *range(1042433, 1042438),
        *range(1062285, 1062290),
        *range(1073629, 1073634),
        *range(1082760, 1082765),
        *range(1103433, 1103438),
        *range(1152212, 1152217),
    }
    genesis = {
        1302355, 1312213, 1322264, 1332289,
        1372237, 1382274, 1402268, 1412189,
        1422197, 1432227, 1442285, 1452266,
        1462252, 1472275, 1482232, 1492245,
    }
    radiance = {1113341, 1122447, 1143471, 1113360, 1012911}
    assert set(rows) == {2000005, *eternal, *genesis, *radiance}
    assert rows[2000005] == (60, 60, 1000000)
    assert all(rows[item_id] == (1, 1, 10000) for item_id in eternal)
    assert all(rows[item_id] == (1, 1, 10000) for item_id in genesis)
    assert all(rows[item_id] == (1, 1, 10000) for item_id in radiance)
    assert "not claimed TMS source probabilities" in sql
