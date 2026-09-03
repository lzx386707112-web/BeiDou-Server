var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 220, maxLevel = 255;
var entryMap = 450004150;
var phaseTwoMap = 450004250;
var exitMap = 450004000;
var recruitMap = 450004000;
var eventTime = 30;
var maxDeaths = 50;
var flowerExplosionInitialDelay = 2000;
var flowerExplosionInterval = 2000;
var flowerExplosionDamageDelay = 1080;
var flowerExplosionDamagePercent = 35;
var flowerExplosionEffects = [
    "customSkill/lucid/flowerExplosionVideoLayer",
    "customSkill/lucid/flowerExplosion1VideoLayer",
    "customSkill/lucid/flowerExplosion2VideoLayer",
    "customSkill/lucid/flowerExplosion3VideoLayer"
];
var fallRecoveryPollInterval = 100;
var fallRecoveryY = 180;

const maxLobbies = 1;
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
const LucidBossCompat = Java.type('org.gms.server.life.LucidBossCompat');
const PacketCreator = Java.type('org.gms.util.PacketCreator');
const AbstractAnimatedMapObject = Java.type('org.gms.server.maps.AbstractAnimatedMapObject');
const Point = Java.type('java.awt.Point');
const ThreadLocalRandom = Java.type('java.util.concurrent.ThreadLocalRandom');

var eventMaps = [entryMap, phaseTwoMap];

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function getEventMaps() {
    var ArrayList = Java.type('java.util.ArrayList');
    var maps = new ArrayList();
    for (var i = 0; i < eventMaps.length; i++) {
        maps.add(eventMaps[i]);
    }
    return maps;
}

function setEventRequirements() {
    em.setProperty("party", "\r\n   Players: 1 ~ 30\r\n   Level: 220 ~ 255\r\n   Time limit: 30 minutes\r\n   Death limit: 50 per character");
}

function setEventExclusives(eim) {
    eim.setExclusiveItems([]);
}

function setEventRewards(eim) {
    eim.setEventRewards(1, [], []);
    eim.setEventClearStageExp([]);
    eim.setEventClearStageMeso([]);
}

function setup(channel) {
    var eim = em.newInstance("LucidBattle" + channel);
    eim.setProperty("canJoin", "1");
    eim.setIntProperty("phase", 1);
    eim.setIntProperty("flowerExplosionVariant", -1);
    for (var i = 0; i < eventMaps.length; i++) {
        var map = eim.getInstanceMap(eventMaps[i]);
        map.resetPQ(1);
        map.killAllMonsters();
    }
    var phaseOneMap = eim.getInstanceMap(entryMap);
    var phaseOneBoss = LifeFactory.getMonster(8880140);
    phaseOneMap.spawnMonsterOnGroundBelow(phaseOneBoss, new Point(1000, 0));
    LucidBossCompat.startPhase(phaseOneMap, phaseOneBoss, 1);
    eim.schedule("castFlowerExplosion", flowerExplosionInitialDelay);
    eim.schedule("recoverFallenPlayers", fallRecoveryPollInterval);
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var id = player.getId();
    if (eim.getIntProperty("eliminated_" + id) == 1) {
        eim.unregisterPlayer(player);
        player.changeMap(exitMap, 0);
        player.dropMessage(5, "露希妲远征死亡次数已达到 50 次。");
        return;
    }
    if (eim.getIntProperty("joined_" + id) == 0) {
        for (var i = 0; i < eventMaps.length; i++) {
            player.resetEnteredScript(eventMaps[i]);
        }
        eim.setIntProperty("death_" + id, 0);
        eim.setIntProperty("joined_" + id, 1);
    }
    var targetMapId = eim.getIntProperty("phase") >= 2 ? phaseTwoMap : entryMap;
    var map = eim.getInstanceMap(targetMapId);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function isEventMap(mapId) {
    return mapId == entryMap || mapId == phaseTwoMap;
}

function changedMap(eim, player, mapId) {
    if (isEventMap(mapId)) {
        return;
    }
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function changedLeader(eim, leader) {}
function playerDead(eim, player) {}

function playerRevive(eim, player) {
    var mapId = player.getMapId();
    if (!isEventMap(mapId)) {
        return true;
    }
    var deathKey = "death_" + player.getId();
    var deaths = eim.getIntProperty(deathKey) + 1;
    eim.setIntProperty(deathKey, deaths);
    if (deaths >= maxDeaths) {
        eim.setIntProperty("eliminated_" + player.getId(), 1);
        player.dropMessage(5, "死亡次数达到 50 次，将返回恶梦时间塔。");
        player.respawn(eim, exitMap);
        disposeIfEmpty(eim);
        return false;
    }

    player.cancelAllBuffs(false);
    player.updateHp(50);
    player.setStance(0);
    player.enableActions();
    var reviveMap = eim.getInstanceMap(mapId);
    reviveMap.movePlayer(player, reviveMap.getPortal(0).getPosition());
    var reviveMovement = PacketCreator.movePlayer(
        player.getId(), player.getIdleMovement(),
        AbstractAnimatedMapObject.IDLE_MOVEMENT_PACKET_LENGTH);
    player.sendPacket(reviveMovement);
    reviveMap.broadcastMessage(player, reviveMovement, false);
    player.dropMessage(5, "露希妲远征死亡次数：" + deaths + "/" + maxDeaths);
    return false;
}

function playerDisconnected(eim, player) {
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function playerUnregistered(eim, player) {}
function leftParty(eim, player) {}
function disbandParty(eim) {}

function monsterValue(eim, mobId) {
    return mobId == 8880140 || mobId == 8880141 || mobId == 8880142 ? 1 : 0;
}

function castFlowerExplosion(eim) {
    if (eim.isEventDisposed() || eim.getIntProperty("phase") != 1) {
        return;
    }
    var map = eim.getInstanceMap(entryMap);
    var boss = map.getMonsterById(8880140);
    if (boss == null || !boss.isAlive()) {
        return;
    }
    map.dropMessage(5, "[Lucid] 花朵爆炸");
    var previous = eim.getIntProperty("flowerExplosionVariant");
    var variant;
    if (previous < 0 || previous >= flowerExplosionEffects.length) {
        variant = ThreadLocalRandom.current().nextInt(flowerExplosionEffects.length);
    } else {
        variant = ThreadLocalRandom.current().nextInt(flowerExplosionEffects.length - 1);
        if (variant >= previous) {
            variant++;
        }
    }
    eim.setIntProperty("flowerExplosionVariant", variant);
    map.broadcastMessage(PacketCreator.showEffect(flowerExplosionEffects[variant]));
    eim.schedule("damageFlowerExplosion", flowerExplosionDamageDelay);
    eim.schedule("castFlowerExplosion", flowerExplosionInterval);
}

function damageFlowerExplosion(eim) {
    if (eim.isEventDisposed() || eim.getIntProperty("phase") != 1) {
        return;
    }
    var map = eim.getInstanceMap(entryMap);
    var boss = map.getMonsterById(8880140);
    if (boss == null || !boss.isAlive()) {
        return;
    }
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        var player = players.get(i);
        if (!player.isAlive() || player.getMap() != map) {
            continue;
        }
        var damage = Math.max(
            1, Math.floor(player.getMaxHp() * flowerExplosionDamagePercent / 100));
        player.addHP(-damage);
        map.broadcastMessage(
            player,
            PacketCreator.damagePlayer(
                0, boss.getId(), player.getId(), damage, 0, 0,
                false, 0, true, boss.getObjectId(), 0, 0),
            false);
    }
}

function recoverFallenPlayers(eim) {
    if (eim.isEventDisposed()) {
        return;
    }
    if (eim.getIntProperty("phase") >= 2) {
        var map = eim.getInstanceMap(phaseTwoMap);
        var destination = map.getPortal(3);
        if (destination != null) {
            var players = eim.getPlayers();
            for (var i = 0; i < players.size(); i++) {
                var player = players.get(i);
                if (player.isAlive() && player.getMap() == map
                        && player.getPosition().y >= fallRecoveryY) {
                    player.changeMap(map, destination);
                }
            }
        }
    }
    eim.schedule("recoverFallenPlayers", fallRecoveryPollInterval);
}

function monsterKilled(mob, eim, hasKiller) {
    if (!hasKiller) {
        return;
    }
    if (mob.getId() == 8880140 && eim.getIntProperty("phase") == 1) {
        eim.setIntProperty("phase", 2);
        eim.dropMessage(5, "[远征队] 露希妲逃进了坍塌的时间塔！");
        eim.schedule("advanceToPhaseTwo", 2500);
    } else if (mob.getId() == 8880142 && !eim.isEventCleared()) {
        clearPQ(eim);
    }
}

function advanceToPhaseTwo(eim) {
    var phaseOneMap = eim.getInstanceMap(entryMap);
    var targetMap = eim.getInstanceMap(phaseTwoMap);
    LucidBossCompat.stop(phaseOneMap);
    phaseOneMap.killAllMonsters();
    targetMap.killAllMonsters();
    var phaseTwoBoss = LifeFactory.getMonster(8880141);
    targetMap.spawnMonsterOnGroundBelow(phaseTwoBoss, new Point(600, -100));
    LucidBossCompat.startPhase(targetMap, phaseTwoBoss, 2);
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        players.get(i).changeMap(targetMap, targetMap.getPortal(0));
    }
}

function allMonstersDead(eim, hasKiller) {}
function monsterRevive(eim, mob) {
    if (mob.getId() == 8880142) {
        eim.setIntProperty("phase", 3);
        LucidBossCompat.startPhase(eim.getInstanceMap(phaseTwoMap), mob, 3);
    }
}

function clearPQ(eim) {
    stopLucidCompat(eim);
    eim.stopEventTimer();
    eim.setProperty("canJoin", "0");
    eim.setEventCleared();
    eim.dropMessage(5, "[远征队] 露希妲已被击败，地图将在 5 分钟后关闭。");
    eim.startEventTimer(300000);
}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    stopLucidCompat(eim);
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        playerExit(eim, players.get(i));
    }
    eim.dispose();
}

function disposeIfEmpty(eim) {
    if (eim.getPlayers().isEmpty()) {
        stopLucidCompat(eim);
        eim.dispose();
    }
}

function stopLucidCompat(eim) {
    for (var i = 0; i < eventMaps.length; i++) {
        LucidBossCompat.stop(eim.getInstanceMap(eventMaps[i]));
    }
}

function giveRandomEventReward(eim, player) {}
function cancelSchedule() {}
function dispose(eim) {}
