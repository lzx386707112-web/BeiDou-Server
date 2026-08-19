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
package org.gms.net.server.channel.handlers;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.client.Disease;
import org.gms.client.inventory.InventoryType;
import org.gms.client.inventory.Item;
import org.gms.client.inventory.manipulator.InventoryManipulator;
import org.gms.config.GameConfig;
import org.gms.constants.id.ItemId;
import org.gms.constants.inventory.ItemConstants;
import org.gms.net.AbstractPacketHandler;
import org.gms.net.packet.InPacket;
import org.gms.scripting.AbstractPlayerInteraction;
import org.gms.scripting.npc.NPCScriptManager;
import org.gms.server.ItemInformationProvider;
import org.gms.server.StatEffect;
import org.gms.util.I18nUtil;
import org.gms.util.PacketCreator;

import static java.util.concurrent.TimeUnit.MINUTES;

/**
 * 处理物品使用逻辑的处理器
 *
 * @author Matze
 */
public final class UseItemHandler extends AbstractPacketHandler {
    private ItemInformationProvider ii = ItemInformationProvider.getInstance();

    @Override
    public final void handlePacket(InPacket p, Client c) {
        Character chr = c.getPlayer();

        // 角色死亡时不处理物品使用
        if (!chr.isAlive()) {
            c.sendPacket(PacketCreator.enableActions());
            return;
        }

        // 读取数据包信息
        p.readInt(); // 跳过无用数据
        short slot = p.readShort();
        int itemId = p.readInt();

        // 验证物品有效性
        Item toUse = chr.getInventory(InventoryType.USE).getItem(slot);
        if (!isValidItem(toUse, itemId)) {
            c.sendPacket(PacketCreator.enableActions());
            return;
        }

        // 处理不同类型物品
        handleItemUsage(chr, c, toUse, slot, itemId);
    }

    /**
     * 验证物品是否有效（存在、数量充足、ID匹配）
     */
    private boolean isValidItem(Item item, int expectedId) {
        return item != null && item.getQuantity() > 0 && item.getItemId() == expectedId;
    }

    /**
     * 分发物品使用逻辑
     */
    private void handleItemUsage(Character chr, Client c, Item item, short slot, int itemId) {
        //处理治愈类物品
        if (handleCureItems(chr, c, slot, itemId)) {
            return;
        }
        //处理怪物卡片（手动使用，加入怪物图鉴）
        if (ItemId.isMonsterCard(itemId)) {
            handleMonsterCard(chr, c, slot, itemId);
            return;
        }
        //处理城镇卷轴
        if (ItemConstants.isTownScroll(itemId)) {
            handleTownScroll(chr, c, slot, itemId);
            return;
        }
        //处理防驱逐卷轴
        if (ItemConstants.isAntibanishScroll(itemId)) {
            handleAntibanishScroll(chr, c, slot, itemId);
            return;
        }
        //处理生日蛋糕
        if (itemId == ItemId.HAPPY_BIRTHDAY) {
            handleBirthdayItem(chr, c, slot, itemId);
            return;
        }
        //处理师徒经验秘药
        if (itemId == ItemId.MENTORSHIP_EXP_POTION) {
            handleExpPotion(chr, c, slot, itemId);
            return;
        }
        //处理消耗品呼出NPC
        if (ii.isNpc(itemId)) {
            handleShortcutMenu(chr, c, slot, itemId);
            return;
        }
        //处理获取其他物品（获取双倍卡）
        if (ii.isHasItem(itemId)) {
            handleHasItem(chr, c, slot, itemId);
            return;
        }
        // 普通物品处理
        handleNormalItem(chr, c, slot, itemId);
    }

    /**
     * 处理治愈类物品
     */
    private boolean handleCureItems(Character chr, Client c, short slot, int itemId) {
        switch (itemId) {
            case ItemId.ALL_CURE_POTION:
                chr.dispelDebuffs();
                removeItem(c, slot);
                return true;
            case ItemId.EYEDROP:
                chr.dispelDebuff(Disease.DARKNESS);
                removeItem(c, slot);
                return true;
            case ItemId.TONIC:
                chr.dispelDebuff(Disease.WEAKEN);
                chr.dispelDebuff(Disease.SLOW);
                removeItem(c, slot);
                return true;
            case ItemId.HOLY_WATER:
                chr.dispelDebuff(Disease.SEAL);
                chr.dispelDebuff(Disease.CURSE);
                removeItem(c, slot);
                return true;
            default:
                return false;
        }
    }

    /**
     * 处理怪物卡片（拾取后在背包中，玩家手动点击使用，加入怪物图鉴）
     */
    private void handleMonsterCard(Character chr, Client c, short slot, int itemId) {
        chr.getMonsterBook().addCard(c, itemId);
        removeItem(c, slot);
    }

    /**
     * 处理城镇卷轴
     */
    private void handleTownScroll(Character chr, Client c, short slot, int itemId) {
        int banMap = chr.getMapId();
        int banSp = chr.getMap().findClosestPlayerSpawnpoint(chr.getPosition()).getId();
        long banTime = currentServerTime();

        if (ii.getItemEffect(itemId).applyTo(chr)) {
            if (GameConfig.getServerBoolean("use_banishable_town_scroll")) {
                chr.setBanishPlayerData(banMap, banSp, banTime);
            }
            removeItem(c, slot);
        }
    }

    /**
     * 处理防驱逐卷轴
     */
    private void handleAntibanishScroll(Character chr, Client c, short slot, int itemId) {
        if (ii.getItemEffect(itemId).applyTo(chr)) {
            removeItem(c, slot);
        } else {
            chr.dropMessage(5, I18nUtil.getMessage("UseItemHandler.message1"));
            c.sendPacket(PacketCreator.enableActions());
        }
    }

    /**
     * 处理生日蛋糕（全地图生效）
     */
    private void handleBirthdayItem(Character chr, Client c, short slot, int itemId) {
        removeItem(c, slot);
        StatEffect effect = ii.getItemEffect(itemId);
        chr.getMap().getCharacters().forEach(player -> effect.applyTo(player));
    }

    private void handleExpPotion(Character chr, Client c, short slot, int itemId) {
        int exp = ii.getExpById(itemId);
        if (exp <= 0) {
            c.sendPacket(PacketCreator.enableActions());
            return;
        }
        removeItem(c, slot);
        chr.gainExp(exp, true, true);
    }

    /**
     * 处理消耗品呼出NPC(如快捷菜单)
     */
    private void handleShortcutMenu(Character chr, Client c, short slot, int itemId) {
        ItemInformationProvider.ScriptedItem info = ii.getScriptedItemInfo(itemId);
        if (info == null) {
            c.sendPacket(PacketCreator.enableActions());
            return;
        }

        if (ii.isRemove(itemId)) {
            removeItem(c, slot);
        } else {
            c.sendPacket(PacketCreator.enableActions());
        }
        NPCScriptManager.getInstance().start(c, info.getNpc(), -1, info.getScript(), chr, false, "cm");
    }

    /**
     * 双倍三倍卡使用后获取效果生效时间半小时
     */
    public void handleHasItem(Character chr, Client c, short slot, int itemId) {
        AbstractPlayerInteraction player = c.getAbstractPlayerInteraction();
        int targetItemId = ii.getHasItemId(itemId);
        int quantity = ii.getHasItemQuantity(itemId);
        int time = ii.getHasItemTime(itemId);
        if (player.canHold(targetItemId, quantity)) {
            player.gainItem(targetItemId, (short) quantity, false, true, MINUTES.toMillis(time));
            if (ii.isRemove(itemId)) {
                removeItem(c, slot);
            } else {
                c.sendPacket(PacketCreator.enableActions());
            }
        } else {
            player.dropMessage(1, "背包空间不足，无法获取");
        }
        c.sendPacket(PacketCreator.enableActions());
    }

    /**
     * 处理普通物品
     */
    private void handleNormalItem(Character chr, Client c, short slot, int itemId) {
        removeItem(c, slot);
        ii.getItemEffect(itemId).applyTo(chr);
    }

    /**
     * 统一处理物品移除和动作启用
     */
    private void removeItem(Client c, short slot) {
        InventoryManipulator.removeFromSlot(c, InventoryType.USE, slot, (short) 1, false);
        c.sendPacket(PacketCreator.enableActions());
    }
}
