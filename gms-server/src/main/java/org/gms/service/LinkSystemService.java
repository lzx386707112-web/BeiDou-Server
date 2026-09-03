package org.gms.service;

import lombok.extern.slf4j.Slf4j;
import org.gms.client.Character;
import org.gms.server.life.Monster;
import org.gms.util.DatabaseConnection;
import org.springframework.stereotype.Service;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
@Slf4j
public class LinkSystemService {
    public static final int FIRST_STAGE_LEVEL = 150;

    public record Bonus(int activeLinks, int allStatPercent, int finalDamagePercent,
                        int bossDamagePercent, int expPercent, int hp, int mp) {
        public static final Bonus NONE = new Bonus(0, 0, 0, 0, 0, 0, 0);

        public float expMultiplier() {
            return (100 + expPercent) / 100.0f;
        }
    }

    public Bonus loadBonus(Character target) {
        if (target == null || target.getId() <= 0) {
            return Bonus.NONE;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            return loadBonus(con, target.getId());
        } catch (SQLException e) {
            log.error("Failed to load Link bonus for character {}", target.getId(), e);
            return Bonus.NONE;
        }
    }

    public String getOverview(Character target) {
        if (target == null) {
            return "角色不存在。";
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            CharacterRecord current = loadCharacter(con, target.getId(), false);
            if (current == null) {
                return "当前角色数据不存在，请重新登录后再试。";
            }

            List<CharacterRecord> characters = loadAccountCharacters(con, current.accountId, current.world);
            Set<Integer> linkedSources = loadLinkedSourceIds(con, current.id);
            int totalSlots = Math.max(loadCharacterSlots(con, current.accountId), characters.size());
            int currentIndex = findCharacterIndex(characters, current.id);
            Bonus bonus = loadBonus(con, current.id);

            StringBuilder text = new StringBuilder("#b#eLink系统#n#k\r\n");
            text.append("当前角色：#b").append(current.name).append("#k Lv.").append(current.level)
                    .append("  槽位 ").append(currentIndex + 1).append("/").append(totalSlots).append("\r\n");
            text.append("已连接：#r").append(linkedSources.size()).append("/")
                    .append(Math.max(0, currentIndex)).append("#k  已生效：#r")
                    .append(bonus.activeLinks).append("#k\r\n\r\n");
            text.append("#e当前总加成#n：全属性 +").append(bonus.allStatPercent).append("%  最终伤害 +")
                    .append(bonus.finalDamagePercent).append("%\r\n")
                    .append("Boss伤害 +").append(bonus.bossDamagePercent).append("%  经验 +")
                    .append(bonus.expPercent).append("%  HP/MP +").append(bonus.hp).append("\r\n\r\n");
            text.append("阶段：Lv.150（3% / 800）  Lv.200（7% / 1500）\r\n")
                    .append("　　　Lv.255（10% / 2000）\r\n\r\n")
                    .append("#eLink槽位#n（只能添加当前角色之前创建的角色）\r\n");

            for (int index = 0; index < totalSlots; index++) {
                text.append("#d").append(index + 1).append(".#k ");
                if (index >= characters.size()) {
                    text.append("#b+ 空槽#k\r\n");
                    continue;
                }
                CharacterRecord slot = characters.get(index);
                if (slot.id == current.id) {
                    text.append("#r◆ ").append(slot.name).append(" Lv.").append(slot.level)
                            .append("（当前角色）#k\r\n");
                    continue;
                }
                if (index > currentIndex) {
                    text.append(slot.name).append(" Lv.").append(slot.level).append("（后序角色）\r\n");
                    continue;
                }

                int percent = stagePercent(slot.level);
                int hpMp = stageHpMp(slot.level);
                if (linkedSources.contains(slot.id)) {
                    if (percent > 0) {
                        text.append("#g◆ ").append(slot.name).append(" Lv.").append(slot.level)
                                .append(" 已生效（+").append(percent).append("% / +")
                                .append(hpMp).append("）#k\r\n");
                    } else {
                        text.append("#k◆ ").append(slot.name).append(" Lv.").append(slot.level)
                                .append(" 已Link，达到Lv.150后生效\r\n");
                    }
                } else if (percent > 0) {
                    text.append(slot.name).append(" Lv.").append(slot.level)
                            .append("  #L").append(slot.id).append("##b+ 添加Link#k#l\r\n");
                } else {
                    text.append(slot.name).append(" Lv.").append(slot.level)
                            .append("（达到Lv.150后可Link）\r\n");
                }
            }
            text.append("\r\n#L-1##b关闭#k#l");
            return text.toString();
        } catch (SQLException e) {
            log.error("Failed to build Link overview for character {}", target.getId(), e);
            return "Link系统暂时不可用，请稍后再试。\r\n\r\n#L-1#关闭#l";
        }
    }

    public String addLink(Character target, int sourceCharacterId) {
        if (target == null || sourceCharacterId <= 0) {
            return "Link角色不存在。";
        }

        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            try {
                CharacterRecord current = loadCharacter(con, target.getId(), true);
                CharacterRecord source = loadCharacter(con, sourceCharacterId, true);
                String validation = validateLink(current, source);
                if (validation != null) {
                    con.rollback();
                    return validation;
                }

                try (PreparedStatement ps = con.prepareStatement(
                        "INSERT IGNORE INTO character_link (target_cid, source_cid) VALUES (?, ?)")) {
                    ps.setInt(1, current.id);
                    ps.setInt(2, source.id);
                    if (ps.executeUpdate() == 0) {
                        con.rollback();
                        return "该角色已经添加过Link。";
                    }
                }

                Bonus bonus = loadBonus(con, current.id);
                con.commit();
                target.refreshLinkBonus(bonus);
                return "已将 #b" + source.name + "#k 添加到Link。\r\n当前总加成：全属性/最终伤害/Boss伤害/经验 +"
                        + bonus.allStatPercent + "% ，HP/MP +" + bonus.hp + "。";
            } catch (SQLException e) {
                con.rollback();
                throw e;
            } finally {
                con.setAutoCommit(true);
            }
        } catch (SQLException e) {
            log.error("Failed to add Link {} -> {}", sourceCharacterId, target.getId(), e);
            return "Link系统暂时不可用，请稍后再试。";
        }
    }

    public static int applyDamage(Character chr, Monster monster, int damage) {
        if (chr == null || damage <= 0 || damage == Integer.MAX_VALUE) {
            return damage;
        }
        return calculateDamage(chr.getLinkBonus(), monster != null && monster.isBoss(), damage);
    }

    static int calculateDamage(Bonus bonus, boolean boss, int damage) {
        if (bonus == null || damage <= 0 || damage == Integer.MAX_VALUE) {
            return damage;
        }
        int percent = bonus.finalDamagePercent;
        if (boss) {
            percent += bonus.bossDamagePercent;
        }
        long result = Math.round(damage * (100.0 + percent) / 100.0);
        return (int) Math.min(Integer.MAX_VALUE, Math.max(1L, result));
    }

    static Bonus calculateBonus(Collection<Integer> sourceLevels) {
        int activeLinks = 0;
        int percent = 0;
        int hpMp = 0;
        for (Integer level : sourceLevels) {
            if (level == null) {
                continue;
            }
            int stagePercent = stagePercent(level);
            if (stagePercent == 0) {
                continue;
            }
            activeLinks++;
            percent += stagePercent;
            hpMp += stageHpMp(level);
        }
        return new Bonus(activeLinks, percent, percent, percent, percent, hpMp, hpMp);
    }

    static int stagePercent(int level) {
        if (level >= 255) {
            return 10;
        }
        if (level >= 200) {
            return 7;
        }
        return level >= FIRST_STAGE_LEVEL ? 3 : 0;
    }

    static int stageHpMp(int level) {
        if (level >= 255) {
            return 2000;
        }
        if (level >= 200) {
            return 1500;
        }
        return level >= FIRST_STAGE_LEVEL ? 800 : 0;
    }

    static boolean isEarlier(Timestamp sourceCreatedAt, int sourceId,
                             Timestamp targetCreatedAt, int targetId) {
        int compared = sourceCreatedAt.compareTo(targetCreatedAt);
        return compared < 0 || (compared == 0 && sourceId < targetId);
    }

    private Bonus loadBonus(Connection con, int targetCharacterId) throws SQLException {
        List<Integer> levels = new ArrayList<>();
        String sql = """
                SELECT source.level
                FROM character_link link_record
                JOIN characters target ON target.id = link_record.target_cid
                JOIN characters source ON source.id = link_record.source_cid
                WHERE target.id = ?
                  AND source.accountid = target.accountid
                  AND source.world = target.world
                  AND (source.createdate < target.createdate
                       OR (source.createdate = target.createdate AND source.id < target.id))
                """;
        try (PreparedStatement ps = con.prepareStatement(sql)) {
            ps.setInt(1, targetCharacterId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    levels.add(rs.getInt("level"));
                }
            }
        }
        return calculateBonus(levels);
    }

    private String validateLink(CharacterRecord target, CharacterRecord source) {
        if (target == null) {
            return "当前角色数据不存在，请重新登录后再试。";
        }
        if (source == null) {
            return "选择的Link角色不存在。";
        }
        if (target.id == source.id) {
            return "不能Link当前角色自己。";
        }
        if (target.accountId != source.accountId || target.world != source.world) {
            return "只能Link同一账号、同一世界的角色。";
        }
        if (!isEarlier(source.createdAt, source.id, target.createdAt, target.id)) {
            return "只能添加比当前角色更早创建的角色。";
        }
        if (source.level < FIRST_STAGE_LEVEL) {
            return "该角色需要达到150级后才能添加Link。";
        }
        return null;
    }

    private CharacterRecord loadCharacter(Connection con, int characterId, boolean forUpdate) throws SQLException {
        String sql = "SELECT id, accountid, world, name, level, createdate FROM characters WHERE id = ?"
                + (forUpdate ? " FOR UPDATE" : "");
        try (PreparedStatement ps = con.prepareStatement(sql)) {
            ps.setInt(1, characterId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? toCharacterRecord(rs) : null;
            }
        }
    }

    private List<CharacterRecord> loadAccountCharacters(Connection con, int accountId, int world) throws SQLException {
        List<CharacterRecord> result = new ArrayList<>();
        try (PreparedStatement ps = con.prepareStatement(
                "SELECT id, accountid, world, name, level, createdate FROM characters "
                        + "WHERE accountid = ? AND world = ? ORDER BY createdate, id")) {
            ps.setInt(1, accountId);
            ps.setInt(2, world);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    result.add(toCharacterRecord(rs));
                }
            }
        }
        return result;
    }

    private Set<Integer> loadLinkedSourceIds(Connection con, int targetCharacterId) throws SQLException {
        Set<Integer> result = new HashSet<>();
        try (PreparedStatement ps = con.prepareStatement(
                "SELECT source_cid FROM character_link WHERE target_cid = ?")) {
            ps.setInt(1, targetCharacterId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    result.add(rs.getInt("source_cid"));
                }
            }
        }
        return result;
    }

    private int loadCharacterSlots(Connection con, int accountId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement(
                "SELECT characterslots FROM accounts WHERE id = ?")) {
            ps.setInt(1, accountId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? Math.max(0, rs.getInt("characterslots")) : 0;
            }
        }
    }

    private static CharacterRecord toCharacterRecord(ResultSet rs) throws SQLException {
        return new CharacterRecord(rs.getInt("id"), rs.getInt("accountid"), rs.getInt("world"),
                rs.getString("name"), rs.getInt("level"), rs.getTimestamp("createdate"));
    }

    private static int findCharacterIndex(List<CharacterRecord> characters, int characterId) {
        for (int index = 0; index < characters.size(); index++) {
            if (characters.get(index).id == characterId) {
                return index;
            }
        }
        return -1;
    }

    private record CharacterRecord(int id, int accountId, int world, String name,
                                   int level, Timestamp createdAt) {
    }
}
