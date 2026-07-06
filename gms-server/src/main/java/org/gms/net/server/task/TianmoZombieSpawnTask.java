/*
 This file is part of the OdinMS Maple Story Server
 Copyright (C) 2008 Patrick Huy <patrick.huy@frz.cc>
 Matthias Butz <matze@odinms.de>
 Jan Christian Meyer <vimes@odinms.de>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as
 published by the Free Software Foundation version 3 as published by
 the Free Software Foundation. You may not use, modify or distribute
 this program under any other version of the GNU Affero General Public
 License.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Affero General Public License for more details.

 You should have received a copy of the GNU Affero General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
package org.gms.net.server.task;

import org.gms.client.Character;
import org.gms.config.GameConfig;
import org.gms.net.server.Server;
import org.gms.net.server.world.World;
import org.gms.server.TimerManager;
import org.gms.server.life.LifeFactory;
import org.gms.server.life.Monster;
import org.gms.server.maps.MapleMap;
import org.gms.util.Randomizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.*;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ScheduledFuture;

import static java.util.concurrent.TimeUnit.MINUTES;
import static java.util.concurrent.TimeUnit.SECONDS;

public final class TianmoZombieSpawnTask implements Runnable {
    private static final Logger log = LoggerFactory.getLogger(TianmoZombieSpawnTask.class);
    private static final TianmoZombieSpawnTask instance = new TianmoZombieSpawnTask();

    private static final int MOB_ID = 9600318;
    private static final int WARNING_EFFECT_ID = 5121009;
    private static final int SPAWN_OFFSET_X = 90;
    private static final long WARNING_DELAY = SECONDS.toMillis(10);
    private static final long DEFAULT_INTERVAL_MINUTES = 120;
    private static final String WARNING_MESSAGE = "天魔僵尸准备，看看哪个倒霉蛋这么好运！";
    private static final String ENABLED_CONFIG = "tianmo_zombie_spawn_enabled";
    private static final String INTERVAL_CONFIG = "tianmo_zombie_spawn_interval_minutes";

    private Monster activeMonster;
    private ScheduledFuture<?> pendingSpawn;
    private ScheduledFuture<?> periodicTask;

    private TianmoZombieSpawnTask() {
    }

    public static TianmoZombieSpawnTask getInstance() {
        return instance;
    }

    public synchronized void start() {
        reload();
    }

    public synchronized void reload() {
        TimerManager timerManager = TimerManager.getInstance();
        timerManager.stop(periodicTask);
        periodicTask = null;

        if (!isEnabled()) {
            timerManager.stop(pendingSpawn);
            pendingSpawn = null;
            return;
        }

        long interval = getIntervalMillis();
        periodicTask = timerManager.register(this, interval, interval);
    }

    @Override
    public synchronized void run() {
        if (!isEnabled()) {
            return;
        }
        if (getEligiblePlayers().isEmpty()) {
            return;
        }

        broadcastWarning();
        TimerManager.getInstance().stop(pendingSpawn);
        pendingSpawn = TimerManager.getInstance().schedule(this::spawnForRandomPlayer, WARNING_DELAY);
    }

    private synchronized void spawnForRandomPlayer() {
        pendingSpawn = null;

        if (!isEnabled()) {
            return;
        }

        List<Character> players = getEligiblePlayers();
        if (players.isEmpty()) {
            return;
        }

        clearActiveMonster();

        Character target = players.get(Randomizer.nextInt(players.size()));
        MapleMap map = target.getMap();
        Monster monster = LifeFactory.getMonster(MOB_ID);
        if (map == null || monster == null) {
            log.warn("Skipped Tianmo Zombie spawn because target map or monster data was unavailable.");
            return;
        }

        Point targetPos = target.getPosition();
        Point spawnPos = new Point(targetPos.x + Randomizer.rand(-SPAWN_OFFSET_X, SPAWN_OFFSET_X), targetPos.y);
        map.spawnMonsterOnGroundBelow(monster, spawnPos);
        activeMonster = monster;

        log.info("Spawned Tianmo Zombie near player {} on map {}", target.getName(), map.getId());
    }

    private void broadcastWarning() {
        for (World world : Server.getInstance().getWorlds()) {
            for (Character chr : world.getPlayerStorage().getAllCharacters()) {
                if (chr != null) {
                    chr.startMapEffect(WARNING_MESSAGE, WARNING_EFFECT_ID);
                }
            }
        }
    }

    private void clearActiveMonster() {
        Monster monster = activeMonster;
        activeMonster = null;
        if (monster == null) {
            return;
        }

        MapleMap map = monster.getMap();
        if (map != null && monster.isAlive()) {
            map.killMonster(monster, null, false);
        }
    }

    private boolean isEnabled() {
        return GameConfig.getServerBoolean(ENABLED_CONFIG);
    }

    private long getIntervalMillis() {
        long configuredMinutes = GameConfig.getServerLong(INTERVAL_CONFIG);
        if (configuredMinutes <= 0) {
            configuredMinutes = DEFAULT_INTERVAL_MINUTES;
        }
        return MINUTES.toMillis(configuredMinutes);
    }

    private List<Character> getEligiblePlayers() {
        List<Character> players = new ArrayList<>();
        for (World world : Server.getInstance().getWorlds()) {
            for (Character chr : world.getPlayerStorage().getAllCharacters()) {
                if (chr != null && chr.isLoggedInWorld() && chr.getMap() != null && chr.isAlive()) {
                    players.add(chr);
                }
            }
        }
        return players;
    }
}
