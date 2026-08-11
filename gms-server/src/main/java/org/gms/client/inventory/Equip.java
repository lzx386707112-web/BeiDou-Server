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
package org.gms.client.inventory;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.alibaba.fastjson2.TypeReference;
import lombok.Getter;
import lombok.Setter;
import org.gms.client.Client;
import org.gms.config.GameConfig;
import org.gms.constants.game.ExpTable;
import org.gms.constants.inventory.ItemConstants;
import org.gms.util.I18nUtil;
import org.gms.util.PacketCreator;
import org.gms.util.Randomizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.gms.server.ItemInformationProvider;
import org.gms.server.EquipmentCubeManager;
import org.gms.util.Pair;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.*;
import java.util.stream.IntStream;

public class Equip extends Item {
    private static final Logger log = LoggerFactory.getLogger(Equip.class);

    public enum ScrollResult {

        FAIL(0), SUCCESS(1), CURSE(2);
        private int value = -1;

        ScrollResult(int value) {
            this.value = value;
        }

        public int getValue() {
            return value;
        }
    }

    /**
     * incDEX：增加敏捷（Dexterity）-dex
     * incSTR：增加力量（Strength）-str
     * incINT：增加智力（Intelligence）-_int
     * incLUK：增加幸运（Luck）-luk
     * incMHP：增加最大生命值（Maximum HP）-hp
     * incMMP：增加最大魔法值（Maximum MP）-mp
     * incPAD：增加物理攻击力（Physical Attack Damage）-watk
     * incMAD：增加魔法攻击力（Magical Attack Damage）-matk
     * incPDD：增加物理防御力（Physical Defense Damage）-wdef
     * incMDD：增加魔法防御力（Magical Defense Damage）-mdef
     * incEVA：增加闪避率（Evasion）-avoid
     * incACC：增加命中率（Accuracy）-acc
     * incSpeed：增加速度（Speed）-speed
     * incJump：增加跳跃力（Jump）-jump
     * incVicious：减少金锤子使用次数（对应游戏中 “vicious” 相关的装备强化限制）
     * incSlot：增加升级槽（可用于砸卷的次数）
     */
    public enum StatUpgrade {

        incDEX(0), incSTR(1), incINT(2), incLUK(3),
        incMHP(4), incMMP(5), incPAD(6), incMAD(7),
        incPDD(8), incMDD(9), incEVA(10), incACC(11),
        incSpeed(12), incJump(13), incVicious(14), incSlot(15);
        private int value = -1;

        StatUpgrade(int value) {
            this.value = value;
        }
    }

    private byte upgradeSlots;
    @Getter
    private byte level, itemLevel;
    private short flag;
    private short str, dex, _int, luk, hp, mp, watk, matk, wdef, mdef, acc, avoid, hands, speed, jump, vicious;
    private float itemExp;
    private int ringid = -1;
    private boolean wear = false;
    private boolean isUpgradeable, isElemental = false;    // timeless or reverse, or any equip that could levelup on GMS for all effects
    private static ItemInformationProvider ii = ItemInformationProvider.getInstance();
    private List<List<Pair<StatUpgrade, Integer>>> mUpgradeHistoryList = new LinkedList<>();
    @Getter
    private String upgradeHistory = "";
    //可额外升级的等级
    @Setter
    @Getter
    private int levelExpand;
    //套装类型
    @Setter
    @Getter
    private int combinationType;
    //混沌卷升级记录
    @Setter
    @Getter
    private String chaosHistory = "";
    //装备吸收历史
    @Setter
    @Getter
    private String absorbHistory = "";
    //
    @Setter
    @Getter
    private int expandAttribute1;
    @Setter
    @Getter
    private int expandAttribute2;
    @Setter
    @Getter
    private String expandAttribute3;
    @Setter
    @Getter
    private String expandAttribute4;
    @Setter
    @Getter
    private int maxStar;//最大星级
    @Setter
    @Getter
    private int starLevel;//当前星级数
    @Setter
    @Getter
    private int starCount;//当前星级数失败次数
    @Setter
    @Getter
    private int upgradeResetCount;//洗练次数
    @Setter
    @Getter
    private int upgradeReturn;//洗练返回次数


    public Equip(int id, short position) {
        this(id, position, 0);
    }

    public Equip(int id, short position, int slots) {
        super(id, position, (short) 1);
        this.upgradeSlots = (byte) slots;
        this.itemExp = 0;
        this.itemLevel = 1;

        this.isElemental = (ii.getEquipLevel(id, false) > 1);
    }

    @Override
    public Item copy() {
        Equip ret = new Equip(getItemId(), getPosition(), getUpgradeSlots());
        ret.str = str;
        ret.dex = dex;
        ret._int = _int;
        ret.luk = luk;
        ret.hp = hp;
        ret.mp = mp;
        ret.matk = matk;
        ret.mdef = mdef;
        ret.watk = watk;
        ret.wdef = wdef;
        ret.acc = acc;
        ret.avoid = avoid;
        ret.hands = hands;
        ret.speed = speed;
        ret.jump = jump;
        ret.flag = flag;
        ret.vicious = vicious;
        ret.upgradeSlots = upgradeSlots;
        ret.itemLevel = itemLevel;
        ret.itemExp = itemExp;
        ret.level = level;
        ret.itemLog = new LinkedList<>(itemLog);
        ret.setOwner(getOwner());
        ret.setQuantity(getQuantity());
        ret.setExpiration(getExpiration());
        ret.setGiftFrom(getGiftFrom());
        ret.setUpgradeHistory(upgradeHistory);
        ret.levelExpand = levelExpand;
        ret.combinationType = combinationType;
        ret.maxStar = maxStar;
        ret.starLevel = starLevel;
        ret.starCount = starCount;
        ret.upgradeResetCount = upgradeResetCount;
        ret.upgradeReturn = upgradeReturn;
        ret.chaosHistory = chaosHistory;
        ret.absorbHistory = absorbHistory;
        ret.expandAttribute1 = expandAttribute1;
        ret.expandAttribute2 = expandAttribute2;
        ret.expandAttribute3 = expandAttribute3;
        ret.expandAttribute4 = expandAttribute4;
        return ret;
    }

    public Equip loadEquipFromDb(Equip equip, ResultSet rs) throws SQLException {
        equip.setOwner(rs.getString("owner"));
        equip.setQuantity((short) 1);
        equip.setAcc((short) rs.getInt("acc"));
        equip.setAvoid((short) rs.getInt("avoid"));
        equip.setDex((short) rs.getInt("dex"));
        equip.setHands((short) rs.getInt("hands"));
        equip.setHp((short) rs.getInt("hp"));
        equip.setInt((short) rs.getInt("int"));
        equip.setJump((short) rs.getInt("jump"));
        equip.setLuk((short) rs.getInt("luk"));
        equip.setMatk((short) rs.getInt("matk"));
        equip.setMdef((short) rs.getInt("mdef"));
        equip.setMp((short) rs.getInt("mp"));
        equip.setSpeed((short) rs.getInt("speed"));
        equip.setStr((short) rs.getInt("str"));
        equip.setWatk((short) rs.getInt("watk"));
        equip.setWdef((short) rs.getInt("wdef"));
        equip.setUpgradeSlots((byte) rs.getInt("upgradeslots"));
        equip.setLevel((byte) rs.getInt("level"));
        equip.setItemLevel(rs.getByte("itemlevel"));
        equip.setItemExp(rs.getInt("itemexp"));
        equip.setRingId(rs.getInt("ringid"));
        equip.setVicious((byte) rs.getInt("vicious"));
        equip.setFlag((short) rs.getInt("flag"));
        equip.setExpiration(rs.getLong("expiration"));
        equip.setGiftFrom(rs.getString("giftFrom"));
        equip.setUpgradeHistory(rs.getString("upgradehistory"));
        //TODO equip 新增属性
        equip.setLevelExpand(rs.getInt("levelExpand"));
        equip.setCombinationType(rs.getInt("combinationType"));
        equip.setMaxStar(rs.getInt("maxStar"));
        equip.setStarLevel(rs.getInt("starLevel"));
        equip.setStarCount(rs.getInt("starCount"));
        equip.setUpgradeResetCount(rs.getInt("upgradeResetCount"));
        equip.setUpgradeReturn(rs.getInt("upgradeReturn"));
        equip.setChaosHistory(rs.getString("chaosHistory"));
        equip.setAbsorbHistory(rs.getString("absorbHistory"));
        equip.setExpandAttribute1(rs.getInt("expandAttribute1"));
        equip.setExpandAttribute2(rs.getInt("expandAttribute2"));
        equip.setExpandAttribute3(rs.getString("expandAttribute3"));
        equip.setExpandAttribute4(rs.getString("expandAttribute4"));
        return equip;
    }

    @Override
    public short getFlag() {
        return flag;
    }

    @Override
    public byte getItemType() {
        return 1;
    }

    public byte getUpgradeSlots() {
        return upgradeSlots;
    }

    public short getStr() {
        return str;
    }

    public short getDex() {
        return dex;
    }

    public short getInt() {
        return _int;
    }

    public short getLuk() {
        return luk;
    }

    public short getHp() {
        return hp;
    }

    public short getMp() {
        return mp;
    }

    public short getWatk() {
        return watk;
    }

    public short getMatk() {
        return matk;
    }

    public short getWdef() {
        return wdef;
    }

    public short getMdef() {
        return mdef;
    }

    public short getAcc() {
        return acc;
    }

    public short getAvoid() {
        return avoid;
    }

    public short getHands() {
        return hands;
    }

    public short getSpeed() {
        return speed;
    }

    public short getJump() {
        return jump;
    }

    public short getVicious() {
        return vicious;
    }

    @Override
    public void setFlag(short flag) {
        this.flag = flag;
    }

    public void setStr(short str) {
        this.str = str;
    }

    public void setDex(short dex) {
        this.dex = dex;
    }

    public void setInt(short _int) {
        this._int = _int;
    }

    public void setLuk(short luk) {
        this.luk = luk;
    }

    public void setHp(short hp) {
        this.hp = hp;
    }

    public void setMp(short mp) {
        this.mp = mp;
    }

    public void setWatk(short watk) {
        this.watk = watk;
    }

    public void setMatk(short matk) {
        this.matk = matk;
    }

    public void setWdef(short wdef) {
        this.wdef = wdef;
    }

    public void setMdef(short mdef) {
        this.mdef = mdef;
    }

    public void setAcc(short acc) {
        this.acc = acc;
    }

    public void setAvoid(short avoid) {
        this.avoid = avoid;
    }

    public void setHands(short hands) {
        this.hands = hands;
    }

    public void setSpeed(short speed) {
        this.speed = speed;
    }

    public void setJump(short jump) {
        this.jump = jump;
    }

    public void setVicious(short vicious) {
        this.vicious = vicious;
    }

    public void setUpgradeSlots(byte upgradeSlots) {
        this.upgradeSlots = upgradeSlots;
    }

    public byte getLevel() {
        return level;
    }

    public void setLevel(byte level) {
        this.level = level;
    }

    private static int getStatModifier(boolean isAttribute) {
        // each set of stat points grants a chance for a bonus stat point upgrade at equip level up.

        if (GameConfig.getServerBoolean("use_equipment_level_up_power")) {
            if (isAttribute) {
                return 2;
            } else {
                return 4;
            }
        } else {
            if (isAttribute) {
                return 4;
            } else {
                return 16;
            }
        }
    }

    /**
     * 老的随机逻辑
     */
    private static int randomizeStatUpgrade(int top) {
        int limit = Math.min(top, GameConfig.getServerInt("max_equipment_level_up_stat_up"));

        int poolCount = (limit * (limit + 1) / 2) + limit;
        int rnd = Randomizer.rand(0, poolCount);

        int stat = 0;
        if (rnd >= limit) {
            rnd -= limit;
            stat = 1 + (int) Math.floor((-1 + Math.sqrt((8 * rnd) + 1)) / 2);    // optimized randomizeStatUpgrade author: David A.
        }

        return stat;
    }

    /**
     * 根据属性升级规则，生成一个加权随机的属性增加值（自定义0概率版）。
     * 特点：
     * 1. 0值的概率可以精确配置，不随maxAllowed变化。
     * 2. 非0值的概率分布保持原版算法的特性（值越小，概率越高）。
     * 3. 采用 O(1) 数学公式进行结果查找，性能极高。
     *
     * @param name 要升级的属性名称。
     * @return 一个在 [0, limit] 范围内的随机整数。
     */
// 假设StatUpgrade、Randomizer是已有类，此处保留方法核心逻辑
    private int randomizeStatUpgradeNew(StatUpgrade name) {
        // 1. 计算基础上限 limit（动态值：5~15）
        int limit = getMaxAllowed(name);
        if (limit <= 0) {
            return 0; // 无增长可能
        }
        // 2. 获取当前激活的属性数量
        int valueQuantity = getValueQuantity();

        // ========== 核心修改1：自定义权重规则（高位减半） ==========
        // 存储1~limit每个值的新权重（double类型适配小数权重）
        double[] newWeights = new double[limit];
        double nonZeroTotalWeight = 0.0; // 新的非零总权重（替换原公式求和）

        for (int x = 1; x <= limit; x++) {
            // 原权重规则：值越小权重越高 → weight = limit - x + 1
            double originalWeight = limit - x + 1;
            // 高位判定：x > limit/2 时权重减半（适配任意limit）
            boolean isHighValue = x > limit / 2.0;
            double currentWeight = isHighValue ? originalWeight / 2.0 : originalWeight;

            newWeights[x - 1] = currentWeight; // x=1对应索引0，x=limit对应索引limit-1
            nonZeroTotalWeight += currentWeight; // 累加新的非零总权重
        }

        // --- 特殊情况处理：当只有一个属性时，必定升级（逻辑微调适配新权重）---
        if (valueQuantity == 1) {
            // 生成1~非零总权重的随机数（适配小数权重，转为int不影响核心逻辑）
            double rnd = Randomizer.nextFloat() * nonZeroTotalWeight;
            // 权重区间匹配（替代原数学公式）
            double cumulative = 0.0;
            int result = limit;
            for (int x = 1; x <= limit; x++) {
                cumulative += newWeights[x - 1];
                if (rnd <= cumulative) {
                    result = x;
                    break;
                }
            }
            return Math.min(Math.max(result, 1), limit);
        }

        // 3. 0值目标概率（逻辑完全不变）
        float targetZeroProbability;
        if (valueQuantity == 2) {
            targetZeroProbability = 0.05f; // 5%
        } else if (valueQuantity == 3) {
            targetZeroProbability = 0.10f; // 10%
        } else if (valueQuantity == 4) {
            targetZeroProbability = 0.15f; // 15%
        } else if (valueQuantity == 5) {
            targetZeroProbability = 0.20f; // 20%
        } else { // valueQuantity >= 6
            targetZeroProbability = 0.25f; // 25%
        }

        // 4. 计算0值权重（逻辑不变，仅基于新的nonZeroTotalWeight）
        double zeroWeight = (targetZeroProbability * nonZeroTotalWeight) / (1.0f - targetZeroProbability);

        // 5. 总权重（改为double类型，避免浮点数精度丢失）
        double totalWeight = zeroWeight + nonZeroTotalWeight;

        // 6. 生成随机数并决定结果
        float randomFloat = Randomizer.nextFloat() * (float) totalWeight;

        // 判断是否为0值（逻辑不变）
        if (randomFloat < zeroWeight) {
            return 0;
        }

        // ========== 核心修改2：权重区间匹配非零值（替代原O(1)公式） ==========
        double adjustedRandom = randomFloat - zeroWeight;
        // 防止浮点数精度问题导致adjustedRandom≤0
        if (adjustedRandom <= 0) {
            return 1;
        }

        // 累加权重匹配结果
        double cumulativeWeight = 0.0;
        int result = limit; // 默认返回最大值（兜底）
        for (int x = 1; x <= limit; x++) {
            cumulativeWeight += newWeights[x - 1];
            // 随机数落入当前值的权重区间，匹配结果
            if (adjustedRandom <= cumulativeWeight) {
                result = x;
                break;
            }
        }

        // 边界保护（逻辑不变）
        return Math.min(Math.max(result, 1), limit);
    }

    private int getMaxAllowed(StatUpgrade name) {
        int maxAllowed = GameConfig.getServerInt("max_equipment_level_up_stat_up");
        //武器得攻击加的更多
        if (getItemId() >= 1300000 && getItemId() < 1800000) {
            if (name == StatUpgrade.incPAD) { //增加物理攻击力
                return (int) Math.round(maxAllowed * 1.6);
            } else if (name == StatUpgrade.incMAD) {//增加魔法攻击力
                return (int) Math.round(maxAllowed * 3.0);
            }
        }
        //智力,防御,血魔,值乘以2
        if (name == StatUpgrade.incINT
                || name == StatUpgrade.incPDD || name == StatUpgrade.incMDD
                || name == StatUpgrade.incMHP || name == StatUpgrade.incMMP) {
            return maxAllowed * 2;
        }
        return maxAllowed;
    }

    public int getValueQuantity() {
        return (int) IntStream.of(dex, str, _int, luk, hp, mp, watk, matk, wdef, mdef, avoid, acc, speed, jump)
                .filter(stat -> stat > 0)
                .count();
    }

    private static boolean isPhysicalWeapon(int itemid) {
        Equip eqp = (Equip) ii.getEquipById(itemid);
        return eqp.getWatk() >= eqp.getMatk();
    }

    private boolean isNotWeaponAffinity(StatUpgrade name) {
        // Vcoc's idea - WATK/MATK expected gains lessens outside of weapon affinity (physical/magic)

        if (ItemConstants.isWeapon(this.getItemId())) {
            if (name.equals(StatUpgrade.incPAD)) {
                return !isPhysicalWeapon(this.getItemId());
            } else if (name.equals(StatUpgrade.incMAD)) {
                return isPhysicalWeapon(this.getItemId());
            }
        }

        return false;
    }

    private void getUnitStatUpgrade(List<Pair<StatUpgrade, Integer>> stats, StatUpgrade name, int curStat, boolean isAttribute) {
        isUpgradeable = true;
        int maxUpgrade = randomizeStatUpgradeNew(name);
        //这里改一下0的时候也记录，防止不加属性，导致不能洗练
//        int maxUpgrade = randomizeStatUpgrade((int) (1 + (curStat / (getStatModifier(isAttribute) * (isNotWeaponAffinity(name) ? 2.7 : 1)))));
//        if (maxUpgrade == 0) {
//            return;
//        }
        stats.add(new Pair<>(name, maxUpgrade));
    }

    /**
     * 尝试为单位插槽添加升级属性（默认10%成功率）
     *
     * @param {List<Pair<StatUpgrade, Integer>>} stats - 存储升级属性的列表（需传入引用）
     * @param {StatUpgrade}           name - 要尝试升级的属性类型
     * @private
     * @static
     * @description 调用重载方法时默认使用10%的成功概率
     */
    private static void getUnitSlotUpgrade(List<Pair<StatUpgrade, Integer>> stats, StatUpgrade name) {
        getUnitSlotUpgrade(stats, name, 0.1);  // 默认10%成功率的快捷调用
    }

    /**
     * 尝试为单位插槽添加升级属性（可配置概率）
     *
     * @param {List<Pair<StatUpgrade, Integer>>} stats - 存储升级属性的列表（需传入引用）
     * @param {StatUpgrade}           name - 要尝试升级的属性类型
     * @param {double}                chance - 成功概率值（范围0.0\~1.0）
     * @private
     * @static
     * @description 通过随机数判断是否成功添加属性升级项
     */
    private static void getUnitSlotUpgrade(List<Pair<StatUpgrade, Integer>> stats, StatUpgrade name, double chance) {
        if (Math.random() <= chance) {  // 概率判定核心逻辑
            stats.add(new Pair<>(name, 1));  // 成功时添加新属性项
        }
    }

    /**
     * 判断是否需要增加砸卷次数或者减少金锤子已使用次数
     */
    private void UpgradeSlotProcessing(List<Pair<StatUpgrade, Integer>> stats, int equipLevel) {
        if (GameConfig.getServerBoolean("use_equipment_level_up_slots")) {// 处理可砸卷次数逻辑
            getUnitSlotUpgrade(stats, StatUpgrade.incSlot); // 增加升级槽
        }
        if (GameConfig.getServerBoolean("use_equipment_level_up_vicious") && vicious > 0) { // 金锤子已使用次数大于0时
            double[][] chanceList = {{0, 255, 0.1}};
            String chanceParam = GameConfig.getServerString("use_equipment_level_up_vicious_levelrange_chance");
            if (chanceParam != null) {
                try {
                    chanceList = JSONObject.parseObject(chanceParam, double[][].class);
                } catch (Throwable e) {
                    log.warn("金锤子装备等级范围概率参数解析失败，请检查是否正确");
                }
            }
            for (double[] obj : chanceList) {
                double minLevel = obj[0], maxLevel = obj[1], chance = obj[2];
                if (equipLevel >= minLevel && equipLevel <= maxLevel) {
                    getUnitSlotUpgrade(stats, StatUpgrade.incVicious, chance); // 减少金锤子
                    break;
                }
            }
        }
    }

    private void improveDefaultStats(List<Pair<StatUpgrade, Integer>> stats) {
        if (dex > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incDEX, dex, true);
        }
        if (str > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incSTR, str, true);
        }
        if (_int > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incINT, _int, true);
        }
        if (luk > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incLUK, luk, true);
        }
        if (hp > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incMHP, hp, false);
        }
        if (mp > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incMMP, mp, false);
        }
        //物理攻击
        if (watk > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incPAD, watk, false);
        }
        //魔法攻击
        if (matk > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incMAD, matk, false);
        }
        if (wdef > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incPDD, wdef, false);
        }
        if (mdef > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incMDD, mdef, false);
        }
        if (avoid > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incEVA, avoid, false);
        }
        if (acc > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incACC, acc, false);
        }
        if (speed > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incSpeed, speed, false);
        }
        if (jump > 0) {
            getUnitStatUpgrade(stats, StatUpgrade.incJump, jump, false);
        }
    }

    public Map<StatUpgrade, Short> getStats() {
        Map<StatUpgrade, Short> stats = new HashMap<>(5);

        if (dex > 0) {
            stats.put(StatUpgrade.incDEX, dex);
        }
        if (str > 0) {
            stats.put(StatUpgrade.incSTR, str);
        }
        if (_int > 0) {
            stats.put(StatUpgrade.incINT, _int);
        }
        if (luk > 0) {
            stats.put(StatUpgrade.incLUK, luk);
        }
        if (hp > 0) {
            stats.put(StatUpgrade.incMHP, hp);
        }
        if (mp > 0) {
            stats.put(StatUpgrade.incMMP, mp);
        }
        if (watk > 0) {
            stats.put(StatUpgrade.incPAD, watk);
        }
        if (matk > 0) {
            stats.put(StatUpgrade.incMAD, matk);
        }
        if (wdef > 0) {
            stats.put(StatUpgrade.incPDD, wdef);
        }
        if (mdef > 0) {
            stats.put(StatUpgrade.incMDD, mdef);
        }
        if (avoid > 0) {
            stats.put(StatUpgrade.incEVA, avoid);
        }
        if (acc > 0) {
            stats.put(StatUpgrade.incACC, acc);
        }
        if (speed > 0) {
            stats.put(StatUpgrade.incSpeed, speed);
        }
        if (jump > 0) {
            stats.put(StatUpgrade.incJump, jump);
        }

        return stats;
    }

    /**
     * 装备升级时计算增加的属性值，值>0才显示，避免显示负数或者0，避免玩家以为属性被扣除了
     * 优化提示消息，使其更易懂
     *
     * @param stats 属性升级列表，包含属性类型和增加值
     * @return 返回一个 Pair，包含提示消息和两个布尔值（是否增加升级槽、是否减少金锤子）
     */
    public Pair<String, Pair<Boolean, Boolean>> gainStats(List<Pair<StatUpgrade, Integer>> stats) {
        boolean gotSlot = false, gotVicious = false; // 标记是否增加了升级槽或减少了金锤子
        StringBuilder lvupStr = new StringBuilder(); // 使用 StringBuilder 提高字符串拼接效率
        int maxStat = GameConfig.getServerInt("max_equipment_stat"); // 获取属性最大值

        for (Pair<StatUpgrade, Integer> stat : stats) { // 遍历属性升级列表
            StatUpgrade type = stat.getLeft(); // 属性类型
            int value = stat.getRight(); // 属性增加值

            switch (type) {
                case incVicious: // 减少金锤子
                    vicious -= value;
                    gotVicious = true;
                    break;
                case incSlot: // 增加升级槽
                    upgradeSlots += value;
                    gotSlot = true;
                    break;
                default: // 处理普通属性
                    if (value != 0) {
                        int statUp = handleStatUpgrade(type, value, maxStat);
                        if (statUp > 0) {
                            lvupStr.append(getStatMessage(type, statUp)).append("; ");
                        }
                    }
                    break;
            }
        }
        return new Pair<>(lvupStr.toString(), new Pair<>(gotSlot, gotVicious));
    }

    /**
     * 处理普通属性的升级逻辑
     *
     * @param type    属性类型
     * @param value   属性增加值
     * @param maxStat 属性最大值
     * @return 实际增加的属性值
     */
    private int handleStatUpgrade(StatUpgrade type, int value, int maxStat) {
        int currentStat = getCurrentStat(type); // 获取当前属性值
        int statUp = Math.min(value, maxStat - currentStat); // 计算实际增加值，不超过最大值
        if (statUp > 0) {
            setCurrentStat(type, currentStat + statUp); // 更新属性值
        }
        return statUp;
    }

    /**
     * 获取当前属性值
     *
     * @param type 属性类型
     * @return 当前属性值
     */
    private int getCurrentStat(StatUpgrade type) {
        switch (type) {
            case incDEX:
                return dex;
            case incSTR:
                return str;
            case incINT:
                return _int;
            case incLUK:
                return luk;
            case incMHP:
                return hp;
            case incMMP:
                return mp;
            case incPAD:
                return watk;
            case incMAD:
                return matk;
            case incPDD:
                return wdef;
            case incMDD:
                return mdef;
            case incEVA:
                return avoid;
            case incACC:
                return acc;
            case incSpeed:
                return speed;
            case incJump:
                return jump;
            default:
                return 0;
        }
    }

    /**
     * 设置当前属性值
     *
     * @param type  属性类型
     * @param value 新的属性值
     */
    private void setCurrentStat(StatUpgrade type, int value) {
        switch (type) {
            case incDEX:
                dex = (short) value;
                break;
            case incSTR:
                str = (short) value;
                break;
            case incINT:
                _int = (short) value;
                break;
            case incLUK:
                luk = (short) value;
                break;
            case incMHP:
                hp = (short) value;
                break;
            case incMMP:
                mp = (short) value;
                break;
            case incPAD:
                watk = (short) value;
                break;
            case incMAD:
                matk = (short) value;
                break;
            case incPDD:
                wdef = (short) value;
                break;
            case incMDD:
                mdef = (short) value;
                break;
            case incEVA:
                avoid = (short) value;
                break;
            case incACC:
                acc = (short) value;
                break;
            case incSpeed:
                speed = (short) value;
                break;
            case incJump:
                jump = (short) value;
                break;
            default:
                break;
        }
    }

    /**
     * 获取属性提升的提示消息
     *
     * @param type  属性类型
     * @param value 属性增加值
     * @return 提示消息
     */
    private String getStatMessage(StatUpgrade type, int value) {
        String messageKey = "Equip.gainStats." + type.name().substring(3); // 从 incDEX 中提取 DEX
        return I18nUtil.getMessage(messageKey) + "+" + value;
    }

    /**
     * 处理装备升级的逻辑，包括属性提升、升级槽增加、金锤子减少等，并通知客户端更新装备状态
     *
     * @param c 触发升级的客户端
     */
    public void gainLevel(Client c) {
        // 这里缺一个校验
        if (mUpgradeHistoryList != null) {
            int size = mUpgradeHistoryList.size();
            if (size > 0 && size != getItemLevel() - 1) {
                itemLevel = (byte) (size + 1);
                c.getPlayer().equipChanged();
                c.getPlayer().forceUpdateItem(this); // 强制更新装备状态
                return;
            }
        }
        List<Pair<StatUpgrade, Integer>> stats = getNewStats(); // 初始化属性升级列表
        itemLevel++; // 提升装备等级
        //记录装备升级信息
        addNewUpgradeHistory(stats);

        String lvupStr = I18nUtil.getMessage("Equip.gainStats.lvupStr", ii.getName(this.getItemId()), itemLevel) + "; ";  // 生成等级提升的提示消息

        Pair<String, Pair<Boolean, Boolean>> res = this.gainStats(stats);    // 调用 gainStats 计算属性提升和生成提示消息
        lvupStr += res.getLeft(); // 拼接属性提升的提示消息
        boolean gotSlot = res.getRight().getLeft(); // 是否增加了升级槽
        boolean gotVicious = res.getRight().getRight(); // 是否减少了金锤子

        if (gotVicious) {// 如果减少了金锤子，追加提示消息
            lvupStr += I18nUtil.getMessage("Equip.gainStats.Vicious", "-1") + "; ";
        }

        if (gotSlot) {// 如果增加了升级槽，追加提示消息
            lvupStr += I18nUtil.getMessage("Equip.gainStats.UPGSLOT", "+1") + "; ";
        }

        // 通知客户端更新装备状态
        c.getPlayer().equipChanged();
        c.getPlayer().showHint(I18nUtil.getMessage("Equip.gainStats.showHint", ii.getName(this.getItemId()), itemLevel), 300); // 显示等级提升的消息
        c.getPlayer().dropMessage(6, lvupStr); // 显示属性提升的消息

        // 发送装备升级的效果包
        c.sendPacket(PacketCreator.showEquipmentLevelUp());
        c.getPlayer().getMap().broadcastPacket(c.getPlayer(), PacketCreator.showForeignEffect(c.getPlayer().getId(), 15));
        c.getPlayer().forceUpdateItem(this); // 强制更新装备状态
    }

    public List<Pair<StatUpgrade, Integer>> getNewStats() {
        List<Pair<StatUpgrade, Integer>> stats = new LinkedList<>(); // 初始化属性升级列表
        int equipLevel = ii.getEquipLevelReq(getItemId()); // 获取装备要求等级

        if (isElemental) {// 如果是元素装备，从配置中获取元素属性升级列表
            List<Pair<String, Integer>> elementalStats = ii.getItemLevelupStats(getItemId(), itemLevel);
            for (Pair<String, Integer> p : elementalStats) {
                if (p.getRight() > 0) { // 只有增加值大于0时才添加到列表
                    stats.add(new Pair<>(StatUpgrade.valueOf(p.getLeft()), p.getRight()));
                }
            }
        }
        if (stats.isEmpty()) {// 如果属性列表为空，则生成默认属性升级列表
            isUpgradeable = false; // 标记装备不可升级
            improveDefaultStats(stats); // 生成默认属性升级列表
        }
        UpgradeSlotProcessing(stats, equipLevel);    // 砸卷次数和减少金锤子次数判断
        if (isUpgradeable && stats.isEmpty()) {// 如果装备仍可升级且属性列表为空，则继续生成属性升级列表
            while (stats.isEmpty()) {
                improveDefaultStats(stats);// 生成默认属性升级列表
                UpgradeSlotProcessing(stats, equipLevel);// 砸卷次数和减少金锤子次数判断
            }
        }
        return stats;
    }

    public int getItemExp() {
        return (int) itemExp;
    }

    private static double normalizedMasteryExp(int reqLevel) {
        // Conversion factor between mob exp and equip exp gain. Through many calculations, the expected for equipment levelup
        // from level 1 to 2 is killing about 100~200 mobs of the same level range, on a 1x EXP rate scenario.

        if (reqLevel < 5) {
            return 42;
        } else if (reqLevel >= 78) {
            return Math.max((10413.648 * Math.exp(reqLevel * 0.03275)), 15);
        } else if (reqLevel >= 38) {
            return Math.max((4985.818 * Math.exp(reqLevel * 0.02007)), 15);
        } else if (reqLevel >= 18) {
            return Math.max((248.219 * Math.exp(reqLevel * 0.11093)), 15);
        } else {
            return Math.max(((1334.564 * Math.log(reqLevel)) - 1731.976), 15);
        }
    }

    /**
     * 获取转生后的装备最大升级次数
     */
    public int getEquipmentMaxLevelUp(Client c) {
        //未涅槃（转生）时装备初始能升级的次数
        int equipMaxLevel = GameConfig.getServerInt("use_equipment_level_up");
        int reborn = c.getPlayer().getReborns();
        //每次转生装备可升级的次数
        int addLevelUp = GameConfig.getServerInt("each_time_reborn_equipment_add_level_up");
        int incremental = reborn * addLevelUp;
        int realMaxLevel = equipMaxLevel + incremental + getLevelExpand();
        return Math.min(realMaxLevel, 100);
    }

    /**
     * 处理装备经验值的增加逻辑（Ronan 的装备经验值获取方法）
     *
     * @param c    客户端对象
     * @param gain 获得的经验值
     */
    public synchronized void gainItemExp(Client c, int gain) {
        if (!ii.isUpgradeable(this.getItemId())) {// 检查装备是否可升级
            return;
        }
        int equipMaxLevel = getEquipmentMaxLevelUp(c);
        if (itemLevel >= equipMaxLevel) {
            return;
        }

        int reqLevel = ii.getEquipLevelReq(this.getItemId());// 获取装备的需求等级

        // 计算经验值修正因子
        float masteryModifier = (GameConfig.getServerFloat("equip_exp_rate") * ExpTable.getExpNeededForLevel(1)) / (float) normalizedMasteryExp(reqLevel);
        float elementModifier = (isElemental) ? 0.85f : 0.6f;

        float baseExpGain = gain * elementModifier * masteryModifier;// 计算实际获得的经验值

        itemExp += baseExpGain;// 更新装备经验值
        int expNeeded = ExpTable.getEquipExpNeededForLevel(itemLevel);

        // 调试信息：显示经验值获取详情
        if (GameConfig.getServerBoolean("use_debug_show_eqp_exp")) {
            log.info("{} -> EXP Gain: {}, Mastery: {}, Base gain: {}, exp: {} / {}, Kills TNL: {}", ii.getName(getItemId()),
                    gain, masteryModifier, baseExpGain, itemExp, expNeeded, expNeeded / (baseExpGain / c.getPlayer().getExpRate()));
        }


        if (itemExp >= expNeeded) {// 判断是否需要升级
            while (itemExp >= expNeeded) {
                itemExp -= expNeeded;
                gainLevel(c); // 升级装备

                if (itemLevel >= equipMaxLevel || !GameConfig.getServerBoolean("use_equipment_level_up_continuous")) {// 如果达到最大等级或者不允许连续升级，重置经验值并退出循环
                    itemExp = 0.0f;
                    break;
                }

                expNeeded = ExpTable.getEquipExpNeededForLevel(itemLevel);// 更新升级所需经验值
            }
        }

        c.getPlayer().forceUpdateItem(this);// 通知客户端更新装备状态
    }

    private boolean reachedMaxLevel(Client c, int maxLevel) {
        if (isElemental) {
            if (itemLevel < ItemInformationProvider.getInstance().getEquipLevel(getItemId(), true)) {
                return false;
            }
        }
        return itemLevel >= maxLevel;
    }

    public String showEquipFeatures(Client c) {
        ItemInformationProvider ii = ItemInformationProvider.getInstance();
        if (!ii.isUpgradeable(this.getItemId())) {
            return "";
        }
        int maxLevel = getEquipmentMaxLevelUp(c);
        String eqpName = ii.getName(getItemId());
        String eqpInfo = reachedMaxLevel(c, maxLevel) ? " #e#rMAX LEVEL = " + maxLevel + "#k#n" : (" EXP: #e#b" + (int) itemExp + "#k#n / " + ExpTable.getEquipExpNeededForLevel(itemLevel) + "   #e#rMAX LEVEL =" + maxLevel);
        return "#k'" + eqpName + "' -> LV: #e#b" + itemLevel + "#k#n    " + eqpInfo + "\r\n";
    }

    public void setItemExp(int exp) {
        this.itemExp = exp;
    }

    public void setItemLevel(byte level) {
        this.itemLevel = level;
    }

    @Override
    public void setQuantity(short quantity) {
        if (quantity < 0 || quantity > 1) {
            throw new RuntimeException("Setting the quantity to " + quantity + " on an equip (itemid: " + getItemId() + ")");
        }
        super.setQuantity(quantity);
    }

    public void setUpgradeSlots(int i) {
        this.upgradeSlots = (byte) i;
    }

    public void setVicious(int i) {
        this.vicious = (short) i;
    }

    public int getRingId() {
        return ringid;
    }

    public void setRingId(int id) {
        this.ringid = id;
    }

    public boolean isWearing() {
        return wear;
    }

    public void wear(boolean yes) {
        wear = yes;
    }


    public String gainStatsDes(List<Pair<StatUpgrade, Integer>> stats) {
        StringBuilder lvupStr = new StringBuilder(); // 使用 StringBuilder 提高字符串拼接效率
        for (Pair<StatUpgrade, Integer> stat : stats) { // 遍历属性升级列表
            StatUpgrade type = stat.getLeft(); // 属性类型
            int value = stat.getRight(); // 属性增加值
            switch (type) {
                case incVicious: // 减少金锤子
                case incSlot: // 增加升级槽
                    break;
                default: // 处理普通属性
                    lvupStr.append(getStatMessage(type, value)).append("; ");
                    break;
            }
        }
        return lvupStr.toString();
    }

    /**
     * 获取升级记录的描述
     */
    public List<String> getUpgradeHistoryDes() {
        List<String> descs = new LinkedList<>();
        for (int i = 0; i < mUpgradeHistoryList.size(); i++) {
            List<Pair<StatUpgrade, Integer>> stats = mUpgradeHistoryList.get(i);
            descs.add(this.gainStatsDes(stats));
        }
        return descs;
    }

    /**
     * 获取升级记录的指定位置描述
     */
    public String getUpgradeHistoryDes(int index) {
        // 1. 先判断集合是否为空
        if (mUpgradeHistoryList == null || mUpgradeHistoryList.isEmpty()) {
            return "暂无升级记录";
        }
        // 2. 判断索引是否合法（0 <= index < 集合长度）
        if (index < 0 || index >= mUpgradeHistoryList.size()) {
            return "升级记录索引无效";
        }
        // 3. 获取对应索引的升级数据，判断是否为空
        List<Pair<StatUpgrade, Integer>> stats = mUpgradeHistoryList.get(index);
        if (stats == null || stats.isEmpty()) {
            return "该次升级无属性变化";
        }
        // 4. 正常生成属性描述
        return this.gainStatsDes(stats);
    }

    public void replaceData(Equip oldItem) {
        // 复制旧装备的核心属性
        setStarLevel(oldItem.getStarLevel());
        setStarCount(oldItem.getStarCount());
        setUpgradeResetCount(oldItem.getUpgradeResetCount());
        setUpgradeHistory(oldItem.getUpgradeHistory());

        // 计算星级对应的属性加成值
        int starLevelAttribute = calculateTotalAttributeByStarLevel();
        // 场景1：升级历史为空 → 所有大于0的属性直接加星级加成
        if (mUpgradeHistoryList.isEmpty()) {
            addStarAttributeToAllValidStats(starLevelAttribute);
            EquipmentCubeManager.inherit(oldItem, this);
            return;
        }
        setItemLevel(oldItem.getItemLevel());
        // 场景2：升级历史非空 → 遍历升级历史叠加属性（保留原有逻辑）
        for (List<Pair<StatUpgrade, Integer>> pairs : mUpgradeHistoryList) {
            for (Pair<StatUpgrade, Integer> pair : pairs) {
                StatUpgrade statType = pair.getLeft();
                int upgradeValue = pair.getRight();
                if (canStarLevel(statType)) {
                    upgradeValue += starLevelAttribute;
                }
                if (upgradeValue <= 0) {
                    continue;
                }
                addAttributeByType(statType, upgradeValue);
            }
        }
        EquipmentCubeManager.inherit(oldItem, this);
    }

    /**
     * 为所有大于0的属性追加星级加成（升级历史为空时调用）
     */
    public void addStarAttributeToAllValidStats(int starAddValue) {
        // 按StatUpgrade枚举全量遍历，确保覆盖所有属性类型
        for (StatUpgrade statType : StatUpgrade.values()) {
            if (canStarLevel(statType)) {
                addAttributeByType(statType, starAddValue);
            }
        }
    }

    public boolean canStarLevel(StatUpgrade statType) {
        return statType == StatUpgrade.incDEX || statType == StatUpgrade.incSTR || statType == StatUpgrade.incINT || statType == StatUpgrade.incLUK
                || statType == StatUpgrade.incPAD || statType == StatUpgrade.incMAD || statType == StatUpgrade.incSpeed;
    }

    /**
     * 根据属性类型追加指定数值（仅当属性当前值>0时生效）
     * 抽离通用逻辑，避免代码冗余
     */
    private void addAttributeByType(StatUpgrade statType, int addValue) {
        if (addValue <= 0) {
            return;
        }
        switch (statType) {
            case incSTR:
                if (getStr() > 0) {
                    setStr((short) (getStr() + addValue));
                }
                break;
            case incDEX:
                if (getDex() > 0) {
                    setDex((short) (getDex() + addValue));
                }
                break;
            case incINT:
                if (getInt() > 0) {
                    setInt((short) (getInt() + addValue));
                }
                break;
            case incLUK:
                if (getLuk() > 0) {
                    setLuk((short) (getLuk() + addValue));
                }
                break;
            case incMHP:
                if (getHp() > 0) {
                    setHp((short) (getHp() + addValue));
                }
                break;
            case incMMP:
                if (getMp() > 0) {
                    setMp((short) (getMp() + addValue));
                }
                break;
            case incPAD:
                if (getWatk() > 0) {
                    setWatk((short) (getWatk() + addValue));
                }
                break;
            case incMAD:
                if (getMatk() > 0) {
                    setMatk((short) (getMatk() + addValue));
                }
                break;
            case incPDD:
                if (getWdef() > 0) {
                    setWdef((short) (getWdef() + addValue));
                }
                break;
            case incMDD:
                if (getMdef() > 0) {
                    setMdef((short) (getMdef() + addValue));
                }
                break;
            case incEVA:
                if (getAvoid() > 0) {
                    setAvoid((short) (getAvoid() + addValue));
                }
                break;
            case incACC:
                if (getAcc() > 0) {
                    setAcc((short) (getAcc() + addValue));
                }
                break;
            case incSpeed:
                if (getSpeed() > 0) {
                    setSpeed((short) (getSpeed() + addValue));
                }
                break;
            case incJump:
                if (getJump() > 0) {
                    setJump((short) (getJump() + addValue));
                }
                break;
            case incVicious:
                if (getVicious() > 0) {
                    setVicious((short) (getVicious() + addValue));
                }
                break;
            case incSlot:
                if (getUpgradeSlots() > 0) {
                    setUpgradeSlots((byte) (getUpgradeSlots() + addValue));
                }
                break;
            default:
                log.warn("Unsupported StatUpgrade type: {}", statType);
                break;
        }
    }

    /**
     * starLevel 1-10属性+1，11-20属性=2，21-30属性=3，31-40属性=4，41-50属性=5
     *
     * @return
     */
    public int calculateTotalAttributeByStarLevel() {
        int starLevel = getStarLevel();
        int totalAttribute = 0;
        // 校验星级合法性（避免负数或超出合理范围的星级）
        if (starLevel <= 0) {
            return 0;
        }
        // 分段计算属性加成
        if (starLevel <= 10) {
            // 1-10级：每级属性+1
            totalAttribute = starLevel * 1;
        } else if (starLevel <= 20) {
            // 11-20级：前10级累计10，11-20级每级+2
            totalAttribute = 10 * 1 + (starLevel - 10) * 2;
        } else if (starLevel <= 30) {
            // 21-30级：前20级累计30（10*1+10*2），21-30级每级+3
            totalAttribute = 10 * 1 + 10 * 2 + (starLevel - 20) * 3;
        } else if (starLevel <= 40) {
            // 31-40级：前30级累计60（10*1+10*2+10*3），31-40级每级+5
            totalAttribute = 10 * 1 + 10 * 2 + 10 * 3 + (starLevel - 30) * 4;
        } else if (starLevel <= 50) {
            // 41-50级：前40级累计110（10*1+10*2+10*3+10*5），41-50级每级+5
            totalAttribute = 10 * 1 + 10 * 2 + 10 * 3 + 10 * 4 + (starLevel - 40) * 5;
        } else {
            // 超出50级的兜底（可根据业务需求调整，比如保持50级的总属性）
            totalAttribute = 10 * 1 + 10 * 2 + 10 * 3 + 10 * 4 + 10 * 5; // 50级满额160
        }

        return totalAttribute;
    }

    /**
     * 设置装备升级历史（从字符串反序列化）
     *
     * @param upgradeHistory 序列化后的升级历史字符串
     */
    public void setUpgradeHistory(String upgradeHistory) {
        if (upgradeHistory != null && !upgradeHistory.trim().isEmpty()) {
            this.upgradeHistory = upgradeHistory;
            mUpgradeHistoryList.clear();
            try {
                // 使用fastjson2反序列化字符串为List<List<Pair>>类型
                List<List<Pair<StatUpgrade, Integer>>> list = JSON.parseObject(
                        upgradeHistory,
                        new TypeReference<List<List<Pair<StatUpgrade, Integer>>>>() {
                        }
                );
                mUpgradeHistoryList.addAll(list);
//                log.info("设置装备升级历史成功：" + mUpgradeHistoryList.toString());
            } catch (Exception e) {
                log.error("解析装备升级历史失败", e);
                mUpgradeHistoryList = new LinkedList<>();
            }
        } else {
            this.upgradeHistory = "";
            mUpgradeHistoryList = new LinkedList<>();
        }
    }

    /**
     * 将升级历史列表序列化为字符串
     *
     * @return 序列化后的升级历史字符串
     */
    public String upgradeHistoryToJson() {
        if (mUpgradeHistoryList == null) {
            log.error("upgradeHistoryToJson序列化为null");
            return "";
        }
        try {
            // 使用fastjson2将列表序列化为字符串
            return JSON.toJSONString(mUpgradeHistoryList);
        } catch (Exception e) {
            log.error("upgradeHistoryToJson 序列化装备升级历史失败", e);
            return "";
        }
    }

    /**
     * 添加新的升级记录到历史列表
     *
     * @param stats 本次升级的属性变化列表
     */
    public void addNewUpgradeHistory(List<Pair<StatUpgrade, Integer>> stats) {
        if (!stats.isEmpty()) {
            if (mUpgradeHistoryList == null) {
                mUpgradeHistoryList = new LinkedList<>();
            }
            mUpgradeHistoryList.add(stats);
            // 同步更新字符串形式的历史记录
            this.upgradeHistory = upgradeHistoryToJson();
        }
    }

    /**
     * 替换装备升级的某一条属性，自动随机生成
     *
     * @param c
     * @param index
     * @return
     */
    public boolean replaceUpgradeHistory(Client c, int index) {
        return replaceUpgradeHistory(c, index, getNewStats());
    }

    /**
     * 替换装备升级历史中第N次的属性记录，并重新应用新属性到装备
     *
     * @param index    要替换的历史记录索引（从0开始）
     * @param newStats 新的属性升级列表
     * @return 替换是否成功
     */
    public boolean replaceUpgradeHistory(Client c, int index, List<Pair<StatUpgrade, Integer>> newStats) {
        // 校验索引有效性和新属性列表非空
        if (mUpgradeHistoryList == null || index < 0 || index >= mUpgradeHistoryList.size() || newStats == null || newStats.isEmpty()) {
            log.warn("替换升级历史失败：无效索引或空属性列表");
            return false;
        }

        // 1. 先移除原第N次升级记录带来的属性
        List<Pair<StatUpgrade, Integer>> oldStats = mUpgradeHistoryList.get(index);
        revertStats(oldStats);

        // 2. 替换历史记录为新属性列表
        mUpgradeHistoryList.set(index, newStats);

        // 3. 应用新的属性列表，并计算属性提升和生成提示消息
        Pair<String, Pair<Boolean, Boolean>> res = this.gainStats(newStats);

        // 4. 同步更新JSON字符串形式的历史记录
        this.upgradeHistory = upgradeHistoryToJson();

        //5.推送成功消息
        String lvupStr = I18nUtil.getMessage("Equip.resetAttributes.lvupStr", ii.getName(this.getItemId())) + "; ";  // 生成等级提升的提示消息
        lvupStr += res.getLeft(); // 拼接属性提升的提示消息
        boolean gotSlot = res.getRight().getLeft(); // 是否增加了升级槽
        boolean gotVicious = res.getRight().getRight(); // 是否减少了金锤子

        if (gotVicious) {// 如果减少了金锤子，追加提示消息
            lvupStr += I18nUtil.getMessage("Equip.gainStats.Vicious", "-1") + "; ";
        }

        if (gotSlot) {// 如果增加了升级槽，追加提示消息
            lvupStr += I18nUtil.getMessage("Equip.gainStats.UPGSLOT", "+1") + "; ";
        }

        // 通知客户端更新装备状态
        c.getPlayer().equipChanged();
        c.getPlayer().showHint(I18nUtil.getMessage("Equip.resetAttributes.showHint", ii.getName(this.getItemId())), 300); // 显示等级提升的消息
        c.getPlayer().dropMessage(6, lvupStr); // 显示属性提升的消息

        // 发送装备升级的效果包
        c.sendPacket(PacketCreator.showEquipmentLevelUp());
        c.getPlayer().getMap().broadcastPacket(c.getPlayer(), PacketCreator.showForeignEffect(c.getPlayer().getId(), 15));
        c.getPlayer().forceUpdateItem(this); // 强制更新装备状态
        return true;
    }

    /**
     * 撤销指定属性列表带来的属性增益（用于替换历史记录时回滚原属性）
     *
     * @param stats 要撤销的属性列表
     */
    private void revertStats(List<Pair<StatUpgrade, Integer>> stats) {
        for (Pair<StatUpgrade, Integer> stat : stats) {
            StatUpgrade type = stat.getLeft();
            int value = stat.getRight();
            if (value <= 0) {
                continue; // 忽略非正值的属性（通常不会出现）
            }

            switch (type) {
                case incVicious:
                    // 原逻辑是减少金锤子次数，撤销则增加
                    vicious += value;
                    break;
                case incSlot:
                    // 原逻辑是增加升级槽，撤销则减少
                    upgradeSlots -= value;
                    if (upgradeSlots < 0) {
                        upgradeSlots = 0; // 防止出现负的升级槽
                    }
                    break;
                default:
                    // 撤销普通属性增益（减去原增加值）
                    int currentStat = getCurrentStat(type);
                    int statDown = Math.min(value, currentStat); // 确保不会减到负数
                    if (statDown > 0) {
                        setCurrentStat(type, currentStat - statDown);
                    }
                    break;
            }
        }
    }

    public String getName() {
        if (ii != null) {

            return ii.getName(this.getItemId());
        } else {
            return "未知道具";
        }
    }
}
