import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_karing_later_stages.py"


def load_migration_module():
    spec = importlib.util.spec_from_file_location("karing_later_stages", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_later_stage_map_order_and_names_are_complete():
    migration = load_migration_module()
    assert migration.MAP_IDS == (
        410007240,
        410007260,
        410007280,
        410007300,
    )
    assert tuple(migration.MAP_NAMES) == tuple(range(410007100, 410007301, 20))


def test_later_stage_maps_drop_unsupported_load_dependencies():
    migration = load_migration_module()
    for map_id in migration.MAP_IDS:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = migration.WzImage.from_bytes(
            path.read_bytes(), key=migration.p1.GMS_KEY, name=path.name
        )
        image.parse()
        assert not image.truncated
        assert image.parse_warnings == []
        assert image.root.child("particle") is None

        back = image.root.child("back")
        if isinstance(back, migration.WzSubProperty):
            assert all(
                int(migration.p1.child_value(entry, "ani") or 0) == 0
                for entry in back.children()
            )

        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if not isinstance(objects, migration.WzSubProperty):
                continue
            for entry in objects.children():
                assert entry.child("spineAni") is None
                assert migration.p1.child_value(entry, "oS") != "BossKaring"

        if map_id in migration.FIGHT_MAP_IDS:
            life = image.root.child("life")
            assert not isinstance(life, migration.WzSubProperty) or not list(life.children())
            portal = image.root.child("portal")
            assert isinstance(portal, migration.WzSubProperty)
            assert {
                migration.p1.child_value(entry, "pn") for entry in portal.children()
            } == {"sp", "ptKaringOut"}
            assert (
                migration.p1.child_value(image.root.child("info"), "fieldLimit")
                == migration.LEGACY_FIGHT_FIELD_LIMIT
            )


def test_later_stage_server_scripts_follow_the_fixed_tms_order():
    expected = {
        "karing_first.js": (410007100, 410007120, 500),
        "goongi_direction.js": (410007120, 410007140, 3480),
        "dool_direction.js": (410007160, 410007180, 500),
        "hondon_direction.js": (410007200, 410007220, 500),
        "karing_direction2.js": (410007240, 410007260, 500),
        "karing_direction3.js": (410007280, 410007300, 500),
    }
    for root_name in ("scripts", "scripts-zh-CN"):
        root = ROOT / "gms-server" / root_name / "map/onUserEnter"
        for filename, values in expected.items():
            text = (root / filename).read_text(encoding="utf-8")
            assert f"scheduleMapWarp({values[0]}, {values[1]}, {values[2]})" in text
            if filename != "goongi_direction.js":
                assert "darkPulseVideoLayer" not in text

    fights = {
        "first_goongipre.js": (8880830, 410007160),
        "first_doolpre.js": (8880831, 410007200),
        "first_hondonpre.js": (8880832, 410007240),
        "first_karing2pre_.js": (8880837, 410007280),
        "first_karing3pre.js": (8880842, -1),
    }
    for root_name in ("scripts", "scripts-zh-CN"):
        root = ROOT / "gms-server" / root_name / "map/onFirstUserEnter"
        for filename, (boss_id, next_map_id) in fights.items():
            text = (root / filename).read_text(encoding="utf-8")
            assert "scheduleKaringBossOnGroundBelowIfMissing" in text
            assert str(boss_id) in text
            assert str(next_map_id) in text


def test_p2_p3_boss_projection_keeps_only_proven_legacy_actions():
    boss_script = ROOT / "tool/scripts/migration/migrate_karing_p1_bosses.py"
    spec = importlib.util.spec_from_file_location("karing_bosses", boss_script)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.LEGACY_CANVAS_SCALE[8880837] == 1.0
    assert migration.LEGACY_CANVAS_SCALE[8880842] == 1.0
    assert migration.LEGACY_MOB_SKILLS[8880837] == ((128, 2, 1),)
    assert migration.LEGACY_MOB_SKILLS[8880842] == ()
    assert migration.LEGACY_ACTION_FRAME_UOLS[8880837] == {
        "attack3": ("stand", ("0",)),
        "attack6": ("stand", ("0",)),
    }
    assert migration.LEGACY_VIDEO_ACTIONS[8880837] == {"regen": (13, 6660)}
    assert migration.LEGACY_VIDEO_ACTIONS[8880842] == {"regen": (14, 8100)}
    assert migration.FULL_DEATH_ACTIONS == {
        8880837: (95, 8550),
        8880842: (134, 12060),
    }
    assert "attack5" not in migration.LEGACY_ACTIONS_ALLOWED[8880842]

    for mob_id in (8880837, 8880842):
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        image = migration.WzImage.from_bytes(
            path.read_bytes(), key=migration.GMS_KEY, name=path.name
        )
        image.parse()
        assert not image.truncated
        assert image.parse_warnings == []
        info = image.root.child("info")
        assert migration.child_value(info, "boss") == 1
        assert migration.child_value(info, "hpTagColor") == 1
        assert migration.child_value(info, "hpTagBgcolor") == 5
        if mob_id == 8880837:
            skills = info.child("skill")
            assert isinstance(skills, migration.WzSubProperty)
            assert [
                (
                    migration.child_value(entry, "skill"),
                    migration.child_value(entry, "level"),
                    migration.child_value(entry, "action"),
                )
                for entry in skills.children()
            ] == [(128, 2, 1)]
            assert image.root.child("skill1") is not None
        else:
            assert info.child("skill") is None
        assert set(migration.action_frame_counts(image)) == migration.LEGACY_ACTIONS_ALLOWED[mob_id]
        die1 = image.root.child("die1")
        frames = sorted(
            (child for child in die1.children() if child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        assert len(frames) == migration.FULL_DEATH_ACTIONS[mob_id][0]
        assert sum(migration.action_frame_delay(die1, frame) for frame in frames) == (
            migration.FULL_DEATH_ACTIONS[mob_id][1]
        )
        resolved_frames = [
            frame if isinstance(frame, migration.WzCanvasProperty)
            else die1.get(str(frame.value))
            for frame in frames
        ]
        assert all(
            isinstance(frame, migration.WzCanvasProperty)
            for frame in resolved_frames
        )
        texture_bytes = sum(
            migration.next_power_of_two(frame.width)
            * migration.next_power_of_two(frame.height)
            * 2
            for frame in resolved_frames
        )
        assert texture_bytes > 250 * 1024 * 1024

        server = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        assert {child.get("name") for child in server if child.get("name") != "info"} == (
            migration.LEGACY_ACTIONS_ALLOWED[mob_id]
        )
        server_die1 = next(child for child in server if child.get("name") == "die1")
        assert sum(child.get("name", "").isdigit() for child in server_die1) == len(frames)


def test_p2_p3_hp_bar_ids_use_their_migrated_icons():
    monster = (ROOT / "gms-server/src/main/java/org/gms/server/life/Monster.java").read_text(
        encoding="utf-8"
    )
    factory = (ROOT / "gms-server/src/main/java/org/gms/server/life/LifeFactory.java").read_text(
        encoding="utf-8"
    )
    hp_packet_source = monster[monster.index("makeBossHPBarPacket"):]
    for mob_id in (8880837, 8880842):
        assert str(mob_id) not in hp_packet_source
        assert str(mob_id) in factory


def test_deleted_reward_map_has_no_runtime_script_or_string_record():
    for tree in ("scripts", "scripts-zh-CN"):
        assert not (
            ROOT / f"gms-server/{tree}/map/onFirstUserEnter/first_karingReward.js"
        ).exists()

    assert not (ROOT / "clien/Data/Map/Map/Map4/410007320.img").exists()
    assert not (
        ROOT / "gms-server/wz/Map.wz/Map/Map4/410007320.img.xml"
    ).exists()
    migration = load_migration_module()
    client = migration.WzImage.from_bytes(
        (ROOT / "clien/Data/String/Map.img").read_bytes(),
        key=migration.p1.GMS_KEY,
        name="Map.img",
    )
    client.parse()
    assert client.root.get("grandis/410007320") is None
    for path in (
        ROOT / "gms-server/wz/String.wz/Map.img.xml",
        ROOT / "gms-server/wz-zh-CN/String.wz/Map.img.xml",
    ):
        grandis = next(
            child for child in ET.parse(path).getroot() if child.get("name") == "grandis"
        )
        assert all(child.get("name") != "410007320" for child in grandis)


def test_karing_move_life_trace_covers_all_five_bosses():
    source = (
        ROOT
        / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MoveLifeHandler.java"
    ).read_text(encoding="utf-8")
    assert "[KaringMoveTrace]" in source
    assert "return pVal >= pMin && pVal <= pMax;" in source
    assert "!(pVal < pMin) || (pVal > pMax)" not in source
    for mob_id in (8880830, 8880831, 8880832, 8880837, 8880842):
        assert str(mob_id) in source


def test_peril_and_clear_scene_markers_are_connected_to_runtime_flow():
    perils = {
        "first_goongipre.js": "perilsGoongiVideoLayer",
        "first_doolpre.js": "perilsDoolVideoLayer",
        "first_hondonpre.js": "perilsHondonVideoLayer",
    }
    for tree in ("scripts", "scripts-zh-CN"):
        root = ROOT / "gms-server" / tree / "map/onFirstUserEnter"
        for filename, marker in perils.items():
            assert f"customSkill/karing/{marker}" in (root / filename).read_text()

    source = (
        ROOT / "gms-server/src/main/java/org/gms/scripting/AbstractPlayerInteraction.java"
    ).read_text(encoding="utf-8")
    for marker in (
        "clearGoongiVideoLayer",
        "clearGoongi2VideoLayer",
        "clearDoolVideoLayer",
        "clearDool2VideoLayer",
        "clearHondonVideoLayer",
        "clearHondon2VideoLayer",
    ):
        assert f"customSkill/karing/{marker}" in source
    assert "960);" in source


def test_karing_scene_marker_accepts_legacy_power_of_two_textures():
    source = (
        ROOT
        / "tool/client-debug/karing-scene-compat/KaringSceneCompat.cpp"
    ).read_text(encoding="utf-8")
    assert "description.Width < kMarkerWidth || description.Width > 8" in source
    assert "description.Height < kMarkerHeight || description.Height > 8" in source
    assert "description.Width != kMarkerWidth" not in source
    assert "description.Height != kMarkerHeight" not in source

    migration = load_migration_module()
    effect = ROOT / "clien/Data/Map/Effect.img"
    image = migration.WzImage.from_bytes(
        effect.read_bytes(), key=migration.p1.GMS_KEY, name=effect.name
    )
    image.parse()
    assert not image.truncated
    assert image.parse_warnings == []
    for marker in (
        "darkPulseVideoLayer",
        "goongiScreenVideoLayer",
        "perilsGoongiVideoLayer",
        "perilsDoolVideoLayer",
        "perilsHondonVideoLayer",
        "rewardScreenVideoLayer",
        "clearGoongiVideoLayer",
        "clearGoongi2VideoLayer",
        "clearDoolVideoLayer",
        "clearDool2VideoLayer",
        "clearHondonVideoLayer",
        "clearHondon2VideoLayer",
    ):
        delay = image.root.get(f"customSkill/karing/{marker}/0/delay")
        assert delay is not None and int(delay.value) == 500


def test_karing_combat_timeline_matches_tms_direct_fields():
    boss_script = ROOT / "tool/scripts/migration/migrate_karing_p1_bosses.py"
    spec = importlib.util.spec_from_file_location("karing_boss_timeline", boss_script)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    expected = {
        8880830: ((15000, 15000, 25000, 0, 0), (30, 35, 60, 100, 30)),
        8880831: ((60000, 15000, 15000, 25000), (100, 40, 30, 20)),
        8880832: ((15000, 12000, 5400, 8000, 12000, 0), (15, 30, 20, 40, 45, 5)),
        8880837: ((12000, 12000, 0, 15000, 30000, 0), (40, 45, 25, 50, 35, 40)),
        8880842: ((12000, 12000, 18000, 15000, 0), (40, 70, 30, 30, 999)),
    }
    regen_durations = {
        8880830: 3240,
        8880831: 2520,
        8880832: 2340,
        8880837: 6660,
        8880842: 8100,
    }
    for mob_id, (cooldowns, damage_rates) in expected.items():
        source = migration.load_image(migration.extract_source(mob_id), migration.BMS_KEY)
        attacks = source.root.get("info/attack")
        assert isinstance(attacks, migration.WzSubProperty)
        assert tuple(
            int(migration.child_value(entry, "cooltime") or 0)
            for entry in attacks.children()
        ) == cooldowns
        assert tuple(
            int(migration.child_value(entry, "fixDamR"))
            for entry in attacks.children()
        ) == damage_rates
        regen = source.root.child("regen")
        assert sum(
            migration.action_frame_delay(regen, frame)
            for frame in regen.children()
            if frame.name.isdigit()
        ) == regen_durations[mob_id]

    goongi = migration.load_image(
        migration.extract_source(8880830), migration.BMS_KEY
    ).root
    assert migration.child_value(goongi.get("info/skill/0"), "skillForbid") == 60000
    assert migration.child_value(goongi.get("info/skill/0"), "afterDelay") == 1560
    assert migration.child_value(goongi.get("info/skill/0"), "attackIdxForSkill") == 3
    assert migration.child_value(goongi.get("info/skill/1"), "skillForbid") == 20000
    assert migration.child_value(goongi.get("info/skill/1"), "skillAfter") == 780


def test_karing_server_separates_impact_timing_from_cooldowns():
    compat = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/KaringBossCompat.java"
    ).read_text(encoding="utf-8")
    factory = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/LifeFactory.java"
    ).read_text(encoding="utf-8")
    monster = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/Monster.java"
    ).read_text(encoding="utf-8")
    movement = (
        ROOT
        / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MoveLifeHandler.java"
    ).read_text(encoding="utf-8")

    assert "attackCooldownMillis(mid, i, impactDelay)" in factory
    assert "KaringBossCompat.isKaringBoss(getId()) && usedAttacks.contains(attackPos)" in monster
    assert "KaringBossCompat.skillCooldownMillis(this, skill)" in monster
    assert "KaringBossCompat.handleProjectedSkillCast" in movement
    assert "GOONGI_SCREEN_EFFECT" in compat
    assert "DARK_PULSE_EFFECT" in compat
    assert "1560," in compat
    assert "100," in compat
    assert "780," in compat
    assert "30," in compat
    assert "2370," in compat
    assert "25," in compat
