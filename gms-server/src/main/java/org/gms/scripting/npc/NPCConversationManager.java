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
package org.gms.scripting.npc;

import lombok.Getter;
import lombok.Setter;
import org.gms.client.Character;
import org.gms.client.*;
import org.gms.client.inventory.Item;
import org.gms.client.inventory.ItemFactory;
import org.gms.client.inventory.Pet;
import org.gms.config.GameConfig;
import org.gms.constants.game.ExpTable;
import org.gms.constants.game.GameConstants;
import org.gms.constants.game.NextLevelType;
import org.gms.constants.id.MapId;
import org.gms.constants.inventory.ItemConstants;
import org.gms.constants.string.LanguageConstants;
import org.gms.manager.ServerManager;
import org.gms.model.pojo.NextLevelContext;
import org.gms.net.server.Server;
import org.gms.net.server.channel.Channel;
import org.gms.net.server.coordinator.matchchecker.MatchCheckerListenerFactory.MatchCheckerType;
import org.gms.net.server.guild.Alliance;
import org.gms.net.server.guild.Guild;
import org.gms.net.server.guild.GuildPackets;
import org.gms.net.server.world.Party;
import org.gms.net.server.world.PartyCharacter;
import org.gms.server.maps.*;
import org.gms.service.GachaponService;
import org.gms.service.PlayerGachaponStatsService;
import org.gms.util.packets.WeddingPackets;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.gms.provider.Data;
import org.gms.provider.DataProviderFactory;
import org.gms.provider.wz.WZFiles;
import org.gms.scripting.AbstractPlayerInteraction;
import org.gms.server.*;
import org.gms.server.SkillbookInformationProvider.SkillBookEntry;
import org.gms.server.events.gm.Event;
import org.gms.server.expeditions.Expedition;
import org.gms.server.expeditions.ExpeditionType;
import org.gms.server.life.LifeFactory;
import org.gms.server.life.PlayerNPC;
import org.gms.server.partyquest.AriantColiseum;
import org.gms.server.partyquest.MonsterCarnival;
import org.gms.server.partyquest.Pyramid;
import org.gms.server.partyquest.Pyramid.PyramidMode;
import org.gms.service.MentorshipService;
import org.gms.service.LinkSystemService;
import org.gms.util.PacketCreator;

import java.awt.*;
import java.sql.SQLException;
import java.util.List;
import java.util.*;

import static java.util.concurrent.TimeUnit.MINUTES;

/**
 * @author Matze
 */
public class NPCConversationManager extends AbstractPlayerInteraction {
    private static final Logger log = LoggerFactory.getLogger(NPCConversationManager.class);

    private final int npc;
    private int npcOid;
    private String scriptName;
    private String getText;
    private boolean itemScript;
    @Setter
    @Getter
    private int itemId;
    private List<PartyCharacter> otherParty;
    private static final GachaponService gachaponService = ServerManager.getApplicationContext().getBean(GachaponService.class);
    private static final PlayerGachaponStatsService playerGachaponStatsService = ServerManager.getApplicationContext().getBean(PlayerGachaponStatsService.class);
    private static final MentorshipService mentorshipService = ServerManager.getApplicationContext().getBean(MentorshipService.class);
    private static final LinkSystemService linkSystemService = ServerManager.getApplicationContext().getBean(LinkSystemService.class);

    private final Map<Integer, String> npcDefaultTalks = new HashMap<>();
    @Getter
    private final NextLevelContext nextLevelContext = new NextLevelContext();
    private String[] mBackpackTypeStr = {"装备", "消耗", "设置", "其他", "特殊"};

    private String getDefaultTalk(int npcid) {
        String talk = npcDefaultTalks.get(npcid);
        if (talk == null) {
            talk = LifeFactory.getNPCDefaultTalk(npcid);
            npcDefaultTalks.put(npcid, talk);
        }

        return talk;
    }

    public NPCConversationManager(Client c, int npc, String scriptName) {
        this(c, npc, -1, scriptName, false);
    }

    public NPCConversationManager(Client c, int npc, List<PartyCharacter> otherParty, boolean test) {
        super(c);
        this.c = c;
        this.npc = npc;
        this.otherParty = otherParty;
    }

    public NPCConversationManager(Client c, int npc, int oid, String scriptName, boolean itemScript) {
        super(c);
        this.npc = npc;
        this.npcOid = oid;
        this.scriptName = scriptName;
        this.itemScript = itemScript;
    }

    public int getNpc() {
        return npc;
    }

    public int[] getDamageSkinIds() {
        return DamageSkinService.getSkinIds();
    }

    public String getDamageSkinName(int skinId) {
        return DamageSkinService.getSkinName(skinId);
    }

    public int getDamageSkinId() {
        return DamageSkinService.getSkinId(getPlayer().getId());
    }

    public String useDamageCapBreakthroughStone() {
        Character player = getPlayer();
        int stoneId = getItemId();
        if (!DamageCapService.isBreakthroughStone(stoneId) || !haveItem(stoneId, 1)) {
            return "突破石不存在，无法使用。";
        }

        DamageCapService.BreakthroughResult result;
        synchronized (player) {
            if (!haveItem(stoneId, 1)) {
                return "突破石不存在，无法使用。";
            }
            result = DamageCapService.attempt(player, stoneId);
            gainItem(stoneId, (short) -1, false);
        }
        player.saveCharToDB(false);

        if (!result.success()) {
            return "突破失败，当前伤害上限仍为 " + result.currentCap() + "。";
        }
        if (!result.changed()) {
            return "突破成功，但增加后会超过 2,147,483,647，当前伤害上限未变化。";
        }
        return "突破成功，伤害上限提升至 " + result.currentCap() + "。";
    }

    public boolean setDamageSkin(int skinId) {
        return DamageSkinService.setSkin(getPlayer(), skinId);
    }

    public int getNpcObjectId() {
        return npcOid;
    }

    public String getScriptName() {
        return scriptName;
    }

    public boolean isItemScript() {
        return itemScript;
    }

    public void resetItemScript() {
        this.itemScript = false;
    }

    public void dispose() {
        nextLevelContext.clear();
        NPCScriptManager.getInstance().dispose(this);
        getClient().sendPacket(PacketCreator.enableActions());
    }

    public void sendNext(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "00 01", (byte) 0));
    }

    public void sendPrev(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "01 00", (byte) 0));
    }

    public void sendNextPrev(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "01 01", (byte) 0));
    }

    public void sendOk(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "00 00", (byte) 0));
    }

    public void sendDefault() {
        sendOk(getDefaultTalk(npc));
    }

    public void sendYesNo(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 1, text, "", (byte) 0));
    }

    public void sendAcceptDecline(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0x0C, text, "", (byte) 0));
    }

    public void sendSimple(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 4, text, "", (byte) 0));
    }

    public void sendNext(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "00 01", speaker));
    }

    public void sendPrev(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "01 00", speaker));
    }

    public void sendNextPrev(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "01 01", speaker));
    }

    public void sendOk(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0, text, "00 00", speaker));
    }

    public void sendYesNo(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 1, text, "", speaker));
    }

    public void sendAcceptDecline(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 0x0C, text, "", speaker));
    }

    public void sendSimple(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalk(npc, (byte) 4, text, "", speaker));
    }

    public void sendStyle(String text, int[] styles) {
        if (styles.length > 0) {
            nextLevelContext.clear();
            getClient().sendPacket(PacketCreator.getNPCTalkStyle(npc, text, styles));
        } else {    // thanks Conrad for noticing empty styles crashing players
            sendOk("Sorry, there are no options of cosmetics available for you here at the moment.");
            dispose();
        }
    }

    public void sendGetNumber(String text, int def, int min, int max) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalkNum(npc, text, def, min, max));
    }

    public void sendGetText(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalkText(npc, text, ""));
    }

    public void sendGetNumber(String text, int def, int min, int max, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalkNum(npc, text, def, min, max, speaker));
    }

    public void sendGetText(String text, byte speaker) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getNPCTalkText(npc, text, "", speaker));
    }

    /*
     * 0 = ariant colliseum
     * 1 = Dojo
     * 2 = Carnival 1
     * 3 = Carnival 2
     * 4 = Ghost Ship PQ?
     * 5 = Pyramid PQ
     * 6 = Kerning Subway
     */
    public void sendDimensionalMirror(String text) {
        nextLevelContext.clear();
        getClient().sendPacket(PacketCreator.getDimensionalMirror(text));
    }

    public void setGetText(String text) {
        this.getText = text;
    }

    public String getText() {
        return this.getText;
    }

    @Override
    public boolean forceStartQuest(int id) {
        return forceStartQuest(id, npc);
    }

    @Override
    public boolean forceCompleteQuest(int id) {
        return forceCompleteQuest(id, npc);
    }

    @Override
    public boolean startQuest(short id) {
        return startQuest((int) id);
    }

    @Override
    public boolean completeQuest(short id) {
        return completeQuest((int) id);
    }

    @Override
    public boolean startQuest(int id) {
        return startQuest(id, npc);
    }

    @Override
    public boolean completeQuest(int id) {
        return completeQuest(id, npc);
    }

    public int getMeso() {
        return getPlayer().getMeso();
    }

    public void gainMeso(int gain) {
        getPlayer().gainMeso(gain);
    }

    public void gainMeso(Double gain) {
        getPlayer().gainMeso(gain.intValue());
    }

    public void gainExp(int gain) {
        getPlayer().gainExp(gain, true, true);
    }

    @Override
    public void showEffect(String effect) {
        getPlayer().getMap().broadcastMessage(PacketCreator.environmentChange(effect, 3));
    }

    public void setHair(int hair) {
        getPlayer().setHair(hair);
        getPlayer().updateSingleStat(Stat.HAIR, hair);
        getPlayer().equipChanged();
    }

    public void setFace(int face) {
        getPlayer().setFace(face);
        getPlayer().updateSingleStat(Stat.FACE, face);
        getPlayer().equipChanged();
    }

    public void setSkin(int color) {
        getPlayer().setSkinColor(SkinColor.getById(color));
        getPlayer().updateSingleStat(Stat.SKIN, color);
        getPlayer().equipChanged();
    }

    public int itemQuantity(int itemid) {
        return getPlayer().getInventory(ItemConstants.getInventoryType(itemid)).countById(itemid);
    }

    public void displayGuildRanks() {
        Guild.displayGuildRanks(getClient(), npc);
    }

    public boolean canSpawnPlayerNpc(int mapid) {
        Character chr = getPlayer();
        return !GameConfig.getServerBoolean("playernpc_auto_deploy") && chr.getLevel() >= chr.getMaxClassLevel() && !chr.isGM() && PlayerNPC.canSpawnPlayerNpc(chr.getName(), mapid);
    }

    public PlayerNPC getPlayerNPCByScriptid(int scriptId) {
        for (MapObject pnpcObj : getPlayer().getMap().getMapObjectsInRange(new Point(0, 0), Double.POSITIVE_INFINITY, Arrays.asList(MapObjectType.PLAYER_NPC))) {
            PlayerNPC pn = (PlayerNPC) pnpcObj;

            if (pn.getScriptId() == scriptId) {
                return pn;
            }
        }

        return null;
    }

    @Override
    public Party getParty() {
        return getPlayer().getParty();
    }

    @Override
    public void resetMap(int mapid) {
        getClient().getChannelServer().getMapFactory().getMap(mapid).resetReactors();
    }

    public void gainTameness(int tameness) {
        for (Pet pet : getPlayer().getPets()) {
            if (pet != null) {
                pet.gainTamenessFullness(getPlayer(), tameness, 0, 0);
            }
        }
    }

    public String getName() {
        return getPlayer().getName();
    }

    public int getGender() {
        return getPlayer().getGender();
    }

    public void changeJobById(int a) {
        getPlayer().changeJob(Job.getById(a));
    }

    public void changeJob(Job job) {
        getPlayer().changeJob(job);
    }

    public String getJobName(int id) {
        return GameConstants.getJobName(id);
    }

    public StatEffect getItemEffect(int itemId) {
        return ItemInformationProvider.getInstance().getItemEffect(itemId);
    }

    public void resetStats() {
        getPlayer().resetStats();
    }

    public void openShopNPC(int id) {
        Shop shop = ShopFactory.getInstance().getShop(id);

        if (shop != null) {
            shop.sendShop(c);
        } else {    // check for missing shopids thanks to resinate
            log.warn("Shop ID: {} is missing from database.", id);
            ShopFactory.getInstance().getShop(11000).sendShop(c);
        }
    }

    public void maxMastery() {
        for (Data skill_ : DataProviderFactory.getDataProvider(WZFiles.STRING).getData("Skill.img").getChildren()) {
            try {
                Skill skill = SkillFactory.getSkill(Integer.parseInt(skill_.getName()));
                getPlayer().changeSkillLevel(skill, (byte) 0, skill.getMaxLevel(), -1);
            } catch (NumberFormatException nfe) {
                nfe.printStackTrace();
                break;
            } catch (NullPointerException npe) {
                npe.printStackTrace();
                continue;
            }
        }
    }

    public void doGachapon() {
        gachaponService.doGachapon(getPlayer(), npc);
    }

    public void doRemoteGachapon(int gachaponId) {
        gachaponService.doGachapon(getPlayer(), gachaponId, false);
    }

    public int getTotalGachaponCount() {
        return playerGachaponStatsService.getTotalCount(getPlayer().getId());
    }

    public String linkSystemOverview() {
        return linkSystemService.getOverview(getPlayer());
    }

    public String linkSystemAdd(int sourceCharacterId) {
        return linkSystemService.addLink(getPlayer(), sourceCharacterId);
    }

    public int getGachaponCount() {
        return playerGachaponStatsService.getGachaponCount(getPlayer().getId());
    }

    public int getRemoteGachaponCount() {
        return playerGachaponStatsService.getRemoteGachaponCount(getPlayer().getId());
    }

    public String mentorshipOverview() {
        return mentorshipService.getOverview(getPlayer());
    }

    public String mentorshipCreate(String targetName) {
        return mentorshipService.createRelation(getPlayer(), targetName);
    }

    public String mentorshipPartyMasterMenu() {
        return mentorshipService.getPartyMasterMenu(getPlayer());
    }

    public boolean mentorshipHasPartyMasterCandidate() {
        return mentorshipService.hasPartyMasterCandidate(getPlayer());
    }

    public String mentorshipCreateFromParty(int masterCid) {
        return mentorshipService.createRelationsFromParty(getPlayer(), masterCid);
    }

    public String mentorshipCancel() {
        return mentorshipService.cancelActiveRelation(getPlayer());
    }

    public String mentorshipClaimStages() {
        return mentorshipService.claimStageRewards(getPlayer());
    }

    public String mentorshipClaimWeekly() {
        return mentorshipService.claimWeeklyPool(getPlayer());
    }

    public String mentorshipStartDuel(int stake) {
        return mentorshipService.startDuel(getPlayer(), stake);
    }

    public String mentorshipJoinDuel(int stakeLimit) {
        return mentorshipService.joinDuel(getPlayer(), stakeLimit);
    }

    public String mentorshipDuelStatus() {
        return mentorshipService.getDuelStatus(getPlayer());
    }

    public String mentorshipRanking(String type) {
        return mentorshipService.getRankingText(type);
    }

    public int mentorshipVirtueCoins() {
        return mentorshipService.getVirtueCoins(getPlayer());
    }

    public int mentorshipApprenticeCoins() {
        return mentorshipService.getApprenticeCoins(getPlayer());
    }

    public boolean mentorshipSpendVirtue(int cost) {
        return mentorshipService.spendVirtueCoins(getPlayer(), cost);
    }

    public boolean mentorshipSpendApprentice(int cost) {
        return mentorshipService.spendApprenticeCoins(getPlayer(), cost);
    }

    public void doGuaranteedGachapon(int poolId, int guaranteedCount) {
        gachaponService.doGuaranteedGachapon(getPlayer(), poolId, guaranteedCount);
    }

    // public void doGachapon() {
    //     GachaponItem item = Gachapon.getInstance().process(npc);
    //     Item itemGained = gainItem(item.getId(), (short) (item.getId() / 10000 == 200 ? 100 : 1), true, true); // For normal potions, make it give 100.
    //
    //     sendNext("你获得了一个 #b#t" + item.getId() + "##k ！");
    //
    //     int[] maps = {MapId.HENESYS, MapId.ELLINIA, MapId.PERION, MapId.KERNING_CITY, MapId.SLEEPYWOOD, MapId.MUSHROOM_SHRINE,
    //             MapId.SHOWA_SPA_M, MapId.SHOWA_SPA_F, MapId.NEW_LEAF_CITY, MapId.NAUTILUS_HARBOR};
    //     final int mapId = maps[(getNpc() != NpcId.GACHAPON_NAUTILUS && getNpc() != NpcId.GACHAPON_NLC) ?
    //             (getNpc() - NpcId.GACHAPON_HENESYS) : getNpc() == NpcId.GACHAPON_NLC ? 8 : 9];
    //     String map = c.getChannelServer().getMapFactory().getMap(mapId).getMapName();
    //
    //     Gachapon.log(getPlayer(), item.getId(), map);
    //
    //     if (item.getTier() > 0) { //Uncommon and Rare
    //         Server.getInstance().broadcastMessage(c.getWorld(), PacketCreator.gachaponMessage(itemGained, map, getPlayer()));
    //     }
    // }

    public void upgradeAlliance() {
        Alliance alliance = Server.getInstance().getAlliance(c.getPlayer().getGuild().getAllianceId());
        alliance.increaseCapacity(1);

        Server.getInstance().allianceMessage(alliance.getId(), GuildPackets.getGuildAlliances(alliance, c.getWorld()), -1, -1);
        Server.getInstance().allianceMessage(alliance.getId(), GuildPackets.allianceNotice(alliance.getId(), alliance.getNotice()), -1, -1);

        c.sendPacket(GuildPackets.updateAllianceInfo(alliance, c.getWorld()));  // thanks Vcoc for finding an alliance update to leader issue
    }

    public void disbandAlliance(Client c, int allianceId) {
        Alliance.disbandAlliance(allianceId);
    }

    public boolean canBeUsedAllianceName(String name) {
        return Alliance.canBeUsedAllianceName(name);
    }

    public Alliance createAlliance(String name) {
        return Alliance.createAlliance(getParty(), name);
    }

    public int getAllianceCapacity() {
        return Server.getInstance().getAlliance(getPlayer().getGuild().getAllianceId()).getCapacity();
    }

    public boolean hasMerchant() {
        return getPlayer().hasMerchant();
    }

    public boolean hasMerchantItems() {
        try {
            if (!ItemFactory.MERCHANT.loadItems(getPlayer().getId(), false).isEmpty()) {
                return true;
            }
        } catch (SQLException e) {
            e.printStackTrace();
            return false;
        }
        return getPlayer().getMerchantMeso() != 0;
    }

    public void showFredrick() {
        c.sendPacket(PacketCreator.getFredrick(getPlayer()));
    }

    public int partyMembersInMap() {
        int inMap = 0;
        for (Character char2 : getPlayer().getMap().getCharacters()) {
            if (char2.getParty() == getPlayer().getParty()) {
                inMap++;
            }
        }
        return inMap;
    }

    public Event getEvent() {
        return c.getChannelServer().getEvent();
    }

    public void divideTeams() {
        if (getEvent() != null) {
            getPlayer().setTeam(getEvent().getLimit() % 2); //muhaha :D
        }
    }

    public Character getMapleCharacter(String player) {
        Character target = Server.getInstance().getWorld(c.getWorld()).getChannel(c.getChannel()).getPlayerStorage().getCharacterByName(player);
        return target;
    }

    public void logLeaf(String prize) {
        MapleLeafLogger.log(getPlayer(), true, prize);
    }

    public boolean createPyramid(String mode, boolean party) {//lol
        PyramidMode mod = PyramidMode.valueOf(mode);

        Party partyz = getPlayer().getParty();
        MapManager mapManager = c.getChannelServer().getMapFactory();

        MapleMap map = null;
        int mapid = MapId.NETTS_PYRAMID_SOLO_BASE;
        if (party) {
            mapid += 10000;
        }
        mapid += (mod.getMode() * 1000);

        for (byte b = 0; b < 5; b++) {//They cannot warp to the next map before the timer ends (:
            map = mapManager.getMap(mapid + b);
            if (map.getCharacters().isEmpty()) {
                return false;
            }
        }

        if (!party) {
            // 修复单人组队金字塔空指针的问题
            PartyCharacter single = new PartyCharacter(getPlayer());
            partyz = new Party(-1, single);
            partyz.addMember(single);
        }
        Pyramid py = new Pyramid(partyz, mod, map.getId());
        getPlayer().setPartyQuest(py);
        py.warp(mapid);
        dispose();
        return true;
    }

    public boolean itemExists(int itemid) {
        return ItemInformationProvider.getInstance().getName(itemid) != null;
    }

    public boolean hasItemData(int itemid) {
        return ItemInformationProvider.getInstance().itemDataExists(itemid);
    }

    public boolean canGenerateItem(int itemid) {
        ItemInformationProvider ii = ItemInformationProvider.getInstance();
        return ii.getName(itemid) != null && ii.itemDataExists(itemid);
    }

    public int getCosmeticItem(int itemid) {
        if (itemExists(itemid)) {
            return itemid;
        }

        int baseid;
        if (itemid < 30000) {
            baseid = (itemid / 1000) * 1000 + (itemid % 100);
        } else {
            baseid = (itemid / 10) * 10;
        }

        return itemid != baseid && itemExists(baseid) ? baseid : -1;
    }

    private int getEquippedCosmeticid(int itemid) {
        if (itemid < 30000) {
            return getPlayer().getFace();
        } else {
            return getPlayer().getHair();
        }
    }

    public boolean isCosmeticEquipped(int itemid) {
        return getEquippedCosmeticid(itemid) == itemid;
    }

    public boolean isUsingOldPqNpcStyle() {
        return GameConfig.getServerBoolean("use_old_gms_styled_pq_npcs") && this.getPlayer().getParty() != null;
    }

    public Object[] getAvailableMasteryBooks() {
        return ItemInformationProvider.getInstance().usableMasteryBooks(this.getPlayer()).toArray();
    }

    public Object[] getAvailableSkillBooks() {
        List<Integer> ret = ItemInformationProvider.getInstance().usableSkillBooks(this.getPlayer());
        ret.addAll(SkillbookInformationProvider.getTeachableSkills(this.getPlayer()));

        return ret.toArray();
    }

    public Object[] getNamesWhoDropsItem(Integer itemId) {
        return ItemInformationProvider.getInstance().getWhoDrops(itemId).toArray();
    }

    public String getSkillBookInfo(int itemid) {
        SkillBookEntry sbe = SkillbookInformationProvider.getSkillbookAvailability(itemid);
        switch (sbe) {
            case UNAVAILABLE:
                return "";

            case REACTOR:
                return "    Obtainable through #rexploring#k (loot boxes).";

            case SCRIPT:
                return "    Obtainable through #rexploring#k (field interaction).";

            case QUEST_BOOK:
                return "    Obtainable through #rquestline#k (collecting book).";

            case QUEST_REWARD:
                return "    Obtainable through #rquestline#k (quest reward).";

            default:
                return "    Obtainable through #rquestline#k.";
        }
    }

    // (CPQ + WED wishlist) by -- Drago (Dragohe4rt)
    public int cpqCalcAvgLvl(int map) {
        int num = 0;
        int avg = 0;
        for (MapObject mmo : c.getChannelServer().getMapFactory().getMap(map).getAllPlayer()) {
            avg += ((Character) mmo).getLevel();
            num++;
        }
        avg /= num;
        return avg;
    }

    public boolean sendCPQMapLists() {
        String msg = LanguageConstants.getMessage(getPlayer(), LanguageConstants.CPQPickRoom);
        int msgLen = msg.length();
        for (int i = 0; i < 6; i++) {
            if (fieldTaken(i)) {
                if (fieldLobbied(i)) {
                    msg += "#b#L" + i + "#Carnival Field " + (i + 1) + " (Level: "  // "Carnival field" GMS-like improvement thanks to Jayd (jaydenseah)
                            + cpqCalcAvgLvl(980000100 + i * 100) + " / "
                            + getPlayerCount(980000100 + i * 100) + "x"
                            + getPlayerCount(980000100 + i * 100) + ")  #l\r\n";
                }
            } else {
                if (i >= 0 && i <= 3) {
                    msg += "#b#L" + i + "#Carnival Field " + (i + 1) + " (2x2) #l\r\n";
                } else {
                    msg += "#b#L" + i + "#Carnival Field " + (i + 1) + " (3x3) #l\r\n";
                }
            }
        }

        if (msg.length() > msgLen) {
            sendSimple(msg);
            return true;
        } else {
            return false;
        }
    }

    public boolean fieldTaken(int field) {
        if (!c.getChannelServer().canInitMonsterCarnival(true, field)) {
            return true;
        }
        if (!c.getChannelServer().getMapFactory().getMap(980000100 + field * 100).getAllPlayer().isEmpty()) {
            return true;
        }
        if (!c.getChannelServer().getMapFactory().getMap(980000101 + field * 100).getAllPlayer().isEmpty()) {
            return true;
        }
        return !c.getChannelServer().getMapFactory().getMap(980000102 + field * 100).getAllPlayer().isEmpty();
    }

    public boolean fieldLobbied(int field) {
        return !c.getChannelServer().getMapFactory().getMap(980000100 + field * 100).getAllPlayer().isEmpty();
    }

    public void cpqLobby(int field) {
        try {
            final MapleMap map, mapExit;
            Channel cs = c.getChannelServer();

            map = cs.getMapFactory().getMap(980000100 + 100 * field);
            mapExit = cs.getMapFactory().getMap(980000000);
            for (PartyCharacter mpc : c.getPlayer().getParty().getMembers()) {
                final Character mc = mpc.getPlayer();
                if (mc != null) {
                    mc.setChallenged(false);
                    mc.changeMap(map, map.getPortal(0));
                    mc.sendPacket(PacketCreator.serverNotice(6, LanguageConstants.getMessage(mc, LanguageConstants.CPQEntryLobby)));
                    TimerManager tMan = TimerManager.getInstance();
                    tMan.schedule(() -> mapClock((int) MINUTES.toSeconds(3)), 1500);

                    mc.setCpqTimer(TimerManager.getInstance().schedule(() -> mc.changeMap(mapExit, mapExit.getPortal(0)), MINUTES.toMillis(3)));
                }
            }
        } catch (Exception ex) {
            ex.printStackTrace();
        }
    }

    public Character getChrById(int id) {
        return c.getChannelServer().getPlayerStorage().getCharacterById(id);
    }

    public void cancelCPQLobby() {
        for (PartyCharacter mpc : c.getPlayer().getParty().getMembers()) {
            Character mc = mpc.getPlayer();
            if (mc != null) {
                mc.clearCpqTimer();
            }
        }
    }

    private void warpoutCPQLobby(MapleMap lobbyMap) {
        MapleMap out = lobbyMap.getChannelServer().getMapFactory().getMap((lobbyMap.getId() < 980030000) ? 980000000 : 980030000);
        for (Character mc : lobbyMap.getAllPlayers()) {
            mc.resetCP();
            mc.setTeam(-1);
            mc.setMonsterCarnival(null);
            mc.changeMap(out, out.getPortal(0));
        }
    }

    private int isCPQParty(MapleMap lobby, Party party) {
        int cpqMinLvl, cpqMaxLvl;

        if (lobby.isCPQLobby()) {
            cpqMinLvl = 30;
            cpqMaxLvl = 50;
        } else {
            cpqMinLvl = 51;
            cpqMaxLvl = 70;
        }

        List<PartyCharacter> partyMembers = party.getPartyMembers();
        for (PartyCharacter pchr : partyMembers) {
            if (pchr.getLevel() >= cpqMinLvl && pchr.getLevel() <= cpqMaxLvl) {
                if (lobby.getCharacterById(pchr.getId()) == null) {
                    return 1;  // party member detected out of area
                }
            } else {
                return 2;  // party member doesn't fit requirements
            }
        }

        return 0;
    }

    private int canStartCPQ(MapleMap lobby, Party party, Party challenger) {
        int ret = isCPQParty(lobby, party);
        if (ret != 0) {
            return ret;
        }

        ret = isCPQParty(lobby, challenger);
        if (ret != 0) {
            return -ret;
        }

        return 0;
    }

    public void startCPQ(final Character challenger, final int field) {
        try {
            cancelCPQLobby();

            final MapleMap lobbyMap = getPlayer().getMap();
            if (challenger != null) {
                if (challenger.getParty() == null) {
                    throw new RuntimeException("No opponent found!");
                }

                for (PartyCharacter mpc : challenger.getParty().getMembers()) {
                    Character mc = mpc.getPlayer();
                    if (mc != null) {
                        mc.changeMap(lobbyMap, lobbyMap.getPortal(0));
                        TimerManager tMan = TimerManager.getInstance();
                        tMan.schedule(() -> mapClock(10), 1500);
                    }
                }
                for (PartyCharacter mpc : getPlayer().getParty().getMembers()) {
                    Character mc = mpc.getPlayer();
                    if (mc != null) {
                        TimerManager tMan = TimerManager.getInstance();
                        tMan.schedule(() -> mapClock(10), 1500);
                    }
                }
            }
            final int mapid = c.getPlayer().getMapId() + 1;
            TimerManager tMan = TimerManager.getInstance();
            tMan.schedule(() -> {
                try {
                    for (PartyCharacter mpc : getPlayer().getParty().getMembers()) {
                        Character mc = mpc.getPlayer();
                        if (mc != null) {
                            mc.setMonsterCarnival(null);
                        }
                    }
                    for (PartyCharacter mpc : challenger.getParty().getMembers()) {
                        Character mc = mpc.getPlayer();
                        if (mc != null) {
                            mc.setMonsterCarnival(null);
                        }
                    }
                } catch (NullPointerException npe) {
                    warpoutCPQLobby(lobbyMap);
                    return;
                }

                Party lobbyParty = getPlayer().getParty(), challengerParty = challenger.getParty();
                int status = canStartCPQ(lobbyMap, lobbyParty, challengerParty);
                if (status == 0) {
                    new MonsterCarnival(lobbyParty, challengerParty, mapid, true, (field / 100) % 10);
                } else {
                    warpoutCPQLobby(lobbyMap);
                }
            }, 11000);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void startCPQ2(final Character challenger, final int field) {
        try {
            cancelCPQLobby();

            final MapleMap lobbyMap = getPlayer().getMap();
            if (challenger != null) {
                if (challenger.getParty() == null) {
                    throw new RuntimeException("No opponent found!");
                }

                for (PartyCharacter mpc : challenger.getParty().getMembers()) {
                    Character mc = mpc.getPlayer();
                    if (mc != null) {
                        mc.changeMap(lobbyMap, lobbyMap.getPortal(0));
                        mapClock(10);
                    }
                }
            }
            final int mapid = c.getPlayer().getMapId() + 100;
            TimerManager tMan = TimerManager.getInstance();
            tMan.schedule(() -> {
                try {
                    for (PartyCharacter mpc : getPlayer().getParty().getMembers()) {
                        Character mc = mpc.getPlayer();
                        if (mc != null) {
                            mc.setMonsterCarnival(null);
                        }
                    }
                    for (PartyCharacter mpc : challenger.getParty().getMembers()) {
                        Character mc = mpc.getPlayer();
                        if (mc != null) {
                            mc.setMonsterCarnival(null);
                        }
                    }
                } catch (NullPointerException npe) {
                    warpoutCPQLobby(lobbyMap);
                    return;
                }

                Party lobbyParty = getPlayer().getParty(), challengerParty = challenger.getParty();
                int status = canStartCPQ(lobbyMap, lobbyParty, challengerParty);
                if (status == 0) {
                    new MonsterCarnival(lobbyParty, challengerParty, mapid, false, (field / 1000) % 10);
                } else {
                    warpoutCPQLobby(lobbyMap);
                }
            }, 10000);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public boolean sendCPQMapLists2() {
        String msg = LanguageConstants.getMessage(getPlayer(), LanguageConstants.CPQPickRoom);
        int msgLen = msg.length();
        for (int i = 0; i < 3; i++) {
            if (fieldTaken2(i)) {
                if (fieldLobbied2(i)) {
                    msg += "#b#L" + i + "#Carnival Field " + (i + 1) + " (Level: "  // "Carnival field" GMS-like improvement thanks to Jayd
                            + cpqCalcAvgLvl(980031000 + i * 1000) + " / "
                            + getPlayerCount(980031000 + i * 1000) + "x"
                            + getPlayerCount(980031000 + i * 1000) + ")  #l\r\n";
                }
            } else {
                if (i == 0 || i == 1) {
                    msg += "#b#L" + i + "#Carnival Field " + (i + 1) + " (2x2) #l\r\n";
                } else {
                    msg += "#b#L" + i + "#Carnival Field " + (i + 1) + " (3x3) #l\r\n";
                }
            }
        }

        if (msg.length() > msgLen) {
            sendSimple(msg);
            return true;
        } else {
            return false;
        }
    }

    public boolean fieldTaken2(int field) {
        if (!c.getChannelServer().canInitMonsterCarnival(false, field)) {
            return true;
        }
        if (!c.getChannelServer().getMapFactory().getMap(980031000 + field * 1000).getAllPlayer().isEmpty()) {
            return true;
        }
        if (!c.getChannelServer().getMapFactory().getMap(980031100 + field * 1000).getAllPlayer().isEmpty()) {
            return true;
        }
        return !c.getChannelServer().getMapFactory().getMap(980031200 + field * 1000).getAllPlayer().isEmpty();
    }

    public boolean fieldLobbied2(int field) {
        return !c.getChannelServer().getMapFactory().getMap(980031000 + field * 1000).getAllPlayer().isEmpty();
    }

    public void cpqLobby2(int field) {
        try {
            final MapleMap map, mapExit;
            Channel cs = c.getChannelServer();

            mapExit = cs.getMapFactory().getMap(980030000);
            map = cs.getMapFactory().getMap(980031000 + 1000 * field);
            for (PartyCharacter mpc : c.getPlayer().getParty().getMembers()) {
                final Character mc = mpc.getPlayer();
                if (mc != null) {
                    mc.setChallenged(false);
                    mc.changeMap(map, map.getPortal(0));
                    mc.sendPacket(PacketCreator.serverNotice(6, LanguageConstants.getMessage(mc, LanguageConstants.CPQEntryLobby)));
                    TimerManager tMan = TimerManager.getInstance();
                    tMan.schedule(() -> mapClock((int) MINUTES.toSeconds(3)), 1500);

                    mc.setCpqTimer(TimerManager.getInstance().schedule(() -> mc.changeMap(mapExit, mapExit.getPortal(0)), MINUTES.toMillis(3)));
                }
            }
        } catch (Exception ex) {
            ex.printStackTrace();
        }
    }

    public void mapClock(int time) {
        getPlayer().getMap().broadcastMessage(PacketCreator.getClock(time));
    }

    private boolean sendCPQChallenge(String cpqType, int leaderid) {
        Set<Integer> cpqLeaders = new HashSet<>();
        cpqLeaders.add(leaderid);
        cpqLeaders.add(getPlayer().getId());

        return c.getWorldServer().getMatchCheckerCoordinator().createMatchConfirmation(MatchCheckerType.CPQ_CHALLENGE, c.getWorld(), getPlayer().getId(), cpqLeaders, cpqType);
    }

    public void answerCPQChallenge(boolean accept) {
        c.getWorldServer().getMatchCheckerCoordinator().answerMatchConfirmation(getPlayer().getId(), accept);
    }

    public void challengeParty2(int field) {
        Character leader = null;
        MapleMap map = c.getChannelServer().getMapFactory().getMap(980031000 + 1000 * field);
        for (MapObject mmo : map.getAllPlayer()) {
            Character mc = (Character) mmo;
            if (mc.getParty() == null) {
                sendOk(LanguageConstants.getMessage(mc, LanguageConstants.CPQFindError));
                return;
            }
            if (mc.getParty().getLeader().getId() == mc.getId()) {
                leader = mc;
                break;
            }
        }
        if (leader != null) {
            if (!leader.isChallenged()) {
                if (!sendCPQChallenge("cpq2", leader.getId())) {
                    sendOk(LanguageConstants.getMessage(leader, LanguageConstants.CPQChallengeRoomAnswer));
                }
            } else {
                sendOk(LanguageConstants.getMessage(leader, LanguageConstants.CPQChallengeRoomAnswer));
            }
        } else {
            sendOk(LanguageConstants.getMessage(leader, LanguageConstants.CPQLeaderNotFound));
        }
    }

    public void challengeParty(int field) {
        Character leader = null;
        MapleMap map = c.getChannelServer().getMapFactory().getMap(980000100 + 100 * field);
        if (map.getAllPlayer().size() != getPlayer().getParty().getMembers().size()) {
            sendOk("An unexpected error regarding the other party has occurred.");
            return;
        }
        for (MapObject mmo : map.getAllPlayer()) {
            Character mc = (Character) mmo;
            if (mc.getParty() == null) {
                sendOk(LanguageConstants.getMessage(mc, LanguageConstants.CPQFindError));
                return;
            }
            if (mc.getParty().getLeader().getId() == mc.getId()) {
                leader = mc;
                break;
            }
        }
        if (leader != null) {
            if (!leader.isChallenged()) {
                if (!sendCPQChallenge("cpq1", leader.getId())) {
                    sendOk(LanguageConstants.getMessage(leader, LanguageConstants.CPQChallengeRoomAnswer));
                }
            } else {
                sendOk(LanguageConstants.getMessage(leader, LanguageConstants.CPQChallengeRoomAnswer));
            }
        } else {
            sendOk(LanguageConstants.getMessage(leader, LanguageConstants.CPQLeaderNotFound));
        }
    }

    private synchronized boolean setupAriantBattle(Expedition exped, int mapid) {
        MapleMap arenaMap = this.getMap().getChannelServer().getMapFactory().getMap(mapid + 1);
        if (!arenaMap.getAllPlayers().isEmpty()) {
            return false;
        }

        new AriantColiseum(arenaMap, exped);
        return true;
    }

    public String startAriantBattle(ExpeditionType expedType, int mapid) {
        if (!GameConstants.isAriantColiseumLobby(mapid)) {
            return "You cannot start an Ariant tournament from outside the Battle Arena Entrance.";
        }

        Expedition exped = this.getMap().getChannelServer().getExpedition(expedType);
        if (exped == null) {
            return "Please register on an expedition before attempting to start an Ariant tournament.";
        }

        List<Character> players = exped.getActiveMembers();

        int playersSize = players.size();
        if (!(playersSize >= exped.getMinSize() && playersSize <= exped.getMaxSize())) {
            return "Make sure there are between #r" + exped.getMinSize() + " ~ " + exped.getMaxSize() + " players#k in this room to start the battle.";
        }

        MapleMap leaderMap = this.getMap();
        for (Character mc : players) {
            if (mc.getMap() != leaderMap) {
                return "All competing players should be on this area to start the battle.";
            }

            if (mc.getParty() != null) {
                return "All competing players must not be on a party to start the battle.";
            }

            int level = mc.getLevel();
            if (!(level >= expedType.getMinLevel() && level <= expedType.getMaxLevel())) {
                return "There are competing players outside of the acceptable level range in this room. All players must be on #blevel between 20~30#k to start the battle.";
            }
        }

        if (setupAriantBattle(exped, mapid)) {
            return "";
        } else {
            return "Other players are already competing on the Ariant tournament in this room. Please wait a while until the arena becomes available again.";
        }
    }

    public void sendMarriageWishlist(boolean groom) {
        Character player = this.getPlayer();
        Marriage marriage = player.getMarriageInstance();
        if (marriage != null) {
            int cid = marriage.getIntProperty(groom ? "groomId" : "brideId");
            Character chr = marriage.getPlayerById(cid);
            if (chr != null) {
                if (chr.getId() == player.getId()) {
                    player.sendPacket(WeddingPackets.onWeddingGiftResult((byte) 0xA, marriage.getWishlistItems(groom), marriage.getGiftItems(player.getClient(), groom)));
                } else {
                    marriage.setIntProperty("wishlistSelection", groom ? 0 : 1);
                    player.sendPacket(WeddingPackets.onWeddingGiftResult((byte) 0x09, marriage.getWishlistItems(groom), marriage.getGiftItems(player.getClient(), groom)));
                }
            }
        }
    }

    public void sendMarriageGifts(List<Item> gifts) {
        this.getPlayer().sendPacket(WeddingPackets.onWeddingGiftResult((byte) 0xA, Collections.singletonList(""), gifts));
    }

    public boolean createMarriageWishlist() {
        Marriage marriage = this.getPlayer().getMarriageInstance();
        if (marriage != null) {
            Boolean groom = marriage.isMarriageGroom(this.getPlayer());
            if (groom != null) {
                String wlKey;
                if (groom) {
                    wlKey = "groomWishlist";
                } else {
                    wlKey = "brideWishlist";
                }

                if (marriage.getProperty(wlKey).contentEquals("")) {
                    getClient().sendPacket(WeddingPackets.sendWishList());
                    return true;
                }
            }
        }

        return false;
    }

    /**
     * 只有下一步的对话
     * 对应sendNext
     *
     * @param nextLevel 下一步方法
     * @param text      对话内容
     */
    public void sendNextLevel(String nextLevel, String text) {
        sendNext(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_NEXT);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 只有上一步的对话
     * 对应sendPrev
     *
     * @param lastLevel 上一步方法
     * @param text      对话内容
     */
    public void sendLastLevel(String lastLevel, String text) {
        sendPrev(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_LAST);
        nextLevelContext.setLastLevel(lastLevel);
    }

    /**
     * 有上一步和下一步的对话
     * 对应sendNextPrev
     *
     * @param lastLevel 上一步方法
     * @param nextLevel 下一步方法
     * @param text      对话内容
     */
    public void sendLastNextLevel(String lastLevel, String nextLevel, String text) {
        sendNextPrev(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_LAST_NEXT);
        nextLevelContext.setLastLevel(lastLevel);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 只有ok按钮的对话
     * 对应sendOk
     *
     * @param nextLevel 点击ok的下一步方法
     * @param text      对话内容
     */
    public void sendOkLevel(String nextLevel, String text) {
        sendOk(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_OK);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 多个选项的对话，选择后自动路由到level + selection对应的方法
     * 对应sendSimple
     *
     * @param text 对话内容
     */
    public void sendSelectLevel(String text) {
        sendSelectLevel("", text);
    }

    /**
     * 多个选项的对话，选择后自动路由到level + prefix + selection对应的方法
     * 对应sendSimple
     *
     * @param prefix 方法前缀，如果脚本有多次要选择的地方，可以通过不同的前缀区分
     * @param text   对话内容
     */
    public void sendSelectLevel(String prefix, String text) {
        sendSimple(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_SELECT);
        nextLevelContext.setPrefix(prefix);
    }

    /**
     * 多个选项的对话，选择后路由到指定方法，将玩家的选择传入
     * 对应sendSimple
     *
     * @param nextLevel 方法前缀，如果脚本有多次要选择的地方，可以通过不同的前缀区分
     * @param text      对话内容
     */
    public void sendNextSelectLevel(String nextLevel, String text) {
        sendSimple(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_NEXT_SELECT);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 获取玩家输入数字的对话
     * 对应sendGetNumber
     *
     * @param nextLevel 下一步方法
     * @param text      对话内容
     * @param def       默认值
     * @param min       最小值
     * @param max       最大值
     */
    public void getInputNumberLevel(String nextLevel, String text, int def, int min, int max) {
        sendGetNumber(text, def, min, max);
        nextLevelContext.setLevelType(NextLevelType.GET_INPUT_NUMBER);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 获取玩家输入字符串的对话
     * 对应sendGetText
     *
     * @param nextLevel 下一步方法
     * @param text      对话内容
     */
    public void getInputTextLevel(String nextLevel, String text) {
        sendGetText(text);
        nextLevelContext.setLevelType(NextLevelType.GET_INPUT_TEXT);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 有接受和拒绝的对话
     * 对应sendAcceptDecline
     *
     * @param decLineLevel 拒绝方法
     * @param acceptLevel  接受方法
     * @param text         对话内容
     */
    public void sendAcceptDeclineLevel(String decLineLevel, String acceptLevel, String text) {
        sendAcceptDecline(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_ACCEPT_DECLINE);
        nextLevelContext.setLastLevel(decLineLevel);
        nextLevelContext.setNextLevel(acceptLevel);
    }

    /**
     * 有是和否的对话
     * 对应sendYesNo
     *
     * @param noLevel  否方法
     * @param yesLevel 是方法
     * @param text     对话内容
     */
    public void sendYesNoLevel(String noLevel, String yesLevel, String text) {
        sendYesNo(text);
        nextLevelContext.setLevelType(NextLevelType.SEND_YES_NO);
        nextLevelContext.setLastLevel(noLevel);
        nextLevelContext.setNextLevel(yesLevel);
    }

    /**
     * 只有下一步的对话
     * 对应sendNext
     *
     * @param nextLevel 下一步方法
     * @param text      对话内容
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendNextLevel(String nextLevel, String text, byte speaker) {
        sendNext(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_NEXT);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 只有上一步的对话
     * 对应sendPrev
     *
     * @param lastLevel 上一步方法
     * @param text      对话内容
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendLastLevel(String lastLevel, String text, byte speaker) {
        sendPrev(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_LAST);
        nextLevelContext.setLastLevel(lastLevel);
    }

    /**
     * 有上一步和下一步的对话
     * 对应sendNextPrev
     *
     * @param lastLevel 上一步方法
     * @param nextLevel 下一步方法
     * @param text      对话内容
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendLastNextLevel(String lastLevel, String nextLevel, String text, byte speaker) {
        sendNextPrev(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_LAST_NEXT);
        nextLevelContext.setLastLevel(lastLevel);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 只有ok按钮的对话
     * 对应sendOk
     *
     * @param nextLevel 点击ok的下一步方法
     * @param text      对话内容
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendOkLevel(String nextLevel, String text, byte speaker) {
        sendOk(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_OK);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 多个选项的对话，选择后自动路由到level + selection对应的方法
     * 对应sendSimple
     *
     * @param text    对话内容
     * @param speaker 说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendSelectLevel(String text, byte speaker) {
        sendSelectLevel("", text, speaker);
    }

    /**
     * 多个选项的对话，选择后自动路由到level + prefix + selection对应的方法
     * 对应sendSimple
     *
     * @param prefix  方法前缀，如果脚本有多次要选择的地方，可以通过不同的前缀区分
     * @param text    对话内容
     * @param speaker 说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendSelectLevel(String prefix, String text, byte speaker) {
        sendSimple(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_SELECT);
        nextLevelContext.setPrefix(prefix);
    }

    /**
     * 多个选项的对话，选择后路由到指定方法，将玩家的选择传入
     * 对应sendSimple
     *
     * @param nextLevel 方法前缀，如果脚本有多次要选择的地方，可以通过不同的前缀区分
     * @param text      对话内容
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendNextSelectLevel(String nextLevel, String text, byte speaker) {
        sendSimple(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_NEXT_SELECT);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 获取玩家输入数字的对话
     * 对应sendGetNumber
     *
     * @param nextLevel 下一步方法
     * @param text      对话内容
     * @param def       默认值
     * @param min       最小值
     * @param max       最大值
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void getPnpcInputNumberLevel(String nextLevel, String text, int def, int min, int max, byte speaker) {
        sendGetNumber(text, def, min, max, speaker);
        nextLevelContext.setLevelType(NextLevelType.GET_INPUT_NUMBER);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 获取玩家输入字符串的对话
     * 对应sendGetText
     *
     * @param nextLevel 下一步方法
     * @param text      对话内容
     * @param speaker   说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void getPnpcInputTextLevel(String nextLevel, String text, byte speaker) {
        sendGetText(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.GET_INPUT_TEXT);
        nextLevelContext.setNextLevel(nextLevel);
    }

    /**
     * 有接受和拒绝的对话
     * 对应sendAcceptDecline
     *
     * @param decLineLevel 拒绝方法
     * @param acceptLevel  接受方法
     * @param text         对话内容
     * @param speaker      说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendAcceptDeclineLevel(String decLineLevel, String acceptLevel, String text, byte speaker) {
        sendAcceptDecline(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_ACCEPT_DECLINE);
        nextLevelContext.setLastLevel(decLineLevel);
        nextLevelContext.setNextLevel(acceptLevel);
    }

    /**
     * 有是和否的对话
     * 对应sendYesNo
     *
     * @param noLevel  否方法
     * @param yesLevel 是方法
     * @param text     对话内容
     * @param speaker  说话者，0,1,8,9 = NPC；2,3 = 玩家；4,5,6,7 = 客户端报38错误；其它数字未测试。
     */
    public void sendYesNoLevel(String noLevel, String yesLevel, String text, byte speaker) {
        sendYesNo(text, speaker);
        nextLevelContext.setLevelType(NextLevelType.SEND_YES_NO);
        nextLevelContext.setLastLevel(noLevel);
        nextLevelContext.setNextLevel(yesLevel);
    }

    public boolean isNotCanHold(int type) {
        return isNotCanHold(type, 2);
    }

    /**
     * 检查背包是否有足够空间
     * type 背包类型:1 装备 2 消耗 3 设置 4 其他 5 特殊
     * count 校验数量
     */
    public boolean isNotCanHold(int type, int count) {
        if (getPlayer().isFull(type, count)) {  // 确保至少有2个空格
            sendOk("#r背包空间不足，请确保#b" + mBackpackTypeStr[type - 1] + "栏#r至少有#b" + count + "#r个空格！");
            dispose();
            return true;
        }
        return false;
    }

    public void forceChangeMap(MapleMap target, Portal pto) {
        getPlayer().forceChangeMap(target, pto);
    }

    public void forceChangeMap(MapleMap target, Point pos) {
        getPlayer().forceChangeMap(target, pos);
    }

    /**
     * 副本进入的最大次数
     */
    public int getPQEnterMaxCount(String maxEnterCountKey) {
        if (maxEnterCountKey == null || maxEnterCountKey.isEmpty()) {
            return 0;
        }
        int count = GameConfig.getServerInt(maxEnterCountKey);
        return count > 0 ? count : 1;
    }

    public String getPQEnteredName(int pqType) {
        String pqKey = "";
        if (pqType == 1) {
            pqKey = "废弃已完成次数";
        } else if (pqType == 2) {
            pqKey = "玩具已完成次数";
        } else if (pqType == 3) {
            pqKey = "海盗已完成次数";
        } else if (pqType == 4) {
            pqKey = "毒物已完成次数";
        } else if (pqType == 5) {
            pqKey = "女神已完成次数";
        } else if (pqType == 6) {
            pqKey = "男女已完成次数";
        } else if (pqType == 7) {
            pqKey = "月妙已完成次数";
        } else if (pqType == 100) {
            pqKey = "蜈蚣已完成次数";
        } else if (pqType == 1000) {
            pqKey = "妖僧已完成次数";
        }
        return pqKey;
    }

    public int getPQEnteredCount(int PQType) {
        return getPQEnteredCount(getPQEnteredName(PQType));
    }

    /**
     * 副本已进入的次数
     */
    public int getPQEnteredCount(String enteredCountKey) {
        if (enteredCountKey == null || enteredCountKey.isEmpty()) {
            return 0;
        }
        String countStr = getCharacterExtendValue(enteredCountKey, true);
        if (countStr == null || countStr.isEmpty()) {
            return 0;
        }
        try {
            return Integer.parseInt(countStr);
        } catch (NumberFormatException e) {
            log.error("getPQCompletedCount:", e);
            return 0;
        }
    }

    public void recordEntryPQ(int PQType) {
        recordEntryPQ(getPQEnteredName(PQType));
    }

    /**
     * 记录进入一次副本
     */
    public void recordEntryPQ(String enteredCountKey) {
        if (enteredCountKey == null || enteredCountKey.isEmpty()) {
            log.error("recordEntryPQ error enteredCountKey is null or empty");
            return;
        }
        saveOrUpdateCharacterExtendValue(enteredCountKey, String.valueOf(getPQEnteredCount(enteredCountKey) + 1), true);
    }

    /**
     * 是否能进入副本
     */
    public boolean canEnterPQ(String enteredCountKey, String maxEnterCountKey) {
        return getPQEnteredCount(enteredCountKey) >= getPQEnterMaxCount(maxEnterCountKey);
    }

    private static final String KEY_JIFEN = "副本积分";
    private static final String KEY_TOTAL_JIFEN = "副本总积分";

    /**
     * 新增一点积分
     */
    public void addPqPoints() {
        addPqPoints(1);
    }

    /**
     * 新增指定点数积分
     */
    public void addPqPoints(int num) {
        saveOrUpdateCharacterExtendValue(KEY_JIFEN, String.valueOf(getPqPoints() + num));
        saveOrUpdateCharacterExtendValue(KEY_TOTAL_JIFEN, String.valueOf(getPqTotalPoints() + num));
    }

    /**
     * 消费当前积分，总积分不变
     *
     * @param num
     */
    public void consumptionPqPoints(int num) {
        int pqPoints = getPqPoints();
        int remaining = pqPoints - num;
        if (remaining < 0) {
            remaining = 0;
        }
        saveOrUpdateCharacterExtendValue(KEY_JIFEN, String.valueOf(remaining));
    }

    /**
     * 获取当前积分
     */
    public int getPqPoints() {
        return parseInt(getCharacterExtendValue(KEY_JIFEN));
    }

    /**
     * 获取总积分
     */
    public int getPqTotalPoints() {
        return parseInt(getCharacterExtendValue(KEY_TOTAL_JIFEN));
    }

    /**
     * 解析字符串变为数字
     */
    public int parseInt(String numStr) {
        if (numStr == null || numStr.isEmpty()) {
            return 0;
        }
        try {
            return Integer.parseInt(numStr);
        } catch (NumberFormatException e) {
            log.error("parseInt:", e);
            return 0;
        }
    }

    /**
     * 副本经验奖励
     * 50-70 获取百分之80经验
     * 70-100级 一次一半经验
     * 100-120 一次3分/1经验
     * 小于50级，一次升1级，50级后所需经验小于200万经验获取当前所需经验的80%，所需经验大于200万获得200万经验。
     *
     * @param maxExp 最大经验 单位是万
     */
    public void gainPQExp(int maxExp) {
        int rewardExp = maxExp * 10000;
        int level = getPlayer().getLevel();
        int needExp = ExpTable.getExpNeededForLevel(level);
        if (needExp < rewardExp) {
            if (level > 50 && level <= 70) {
                rewardExp = (int) (needExp * 0.8);
            } else if (level > 70 && level <= 100) {
                rewardExp = (int) (needExp * 0.5);
            } else if (level > 100 && level <= 124) {
                rewardExp = (int) (needExp * 0.3);
            } else {
                rewardExp = needExp;
            }
        }
        gainExp(rewardExp);
    }

}
