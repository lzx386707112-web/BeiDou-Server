package org.gms.service;

import lombok.extern.slf4j.Slf4j;
import org.gms.client.Character;
import org.gms.net.server.Server;
import org.gms.server.CashShop;
import org.gms.util.DatabaseConnection;
import org.springframework.stereotype.Service;

import java.sql.*;
import java.time.LocalDate;
import java.time.temporal.WeekFields;
import java.util.*;

@Service
@Slf4j
public class MentorshipService {
    private static final int STATUS_ACTIVE = 0;
    private static final int STATUS_GRADUATED = 1;
    private static final int STATUS_CANCELLED = 2;
    private static final int MASTER_MIN_LEVEL = 200;
    private static final int MIN_DUEL_STAKE = 100;
    private static final int GPQ_CLEAR_POINTS = 100;
    private static final int WEEKLY_CLAIM_UNIT = 100;
    private static final int WEEKLY_MASTER_VIRTUE_PER_UNIT = 8;
    private static final int WEEKLY_APPRENTICE_COIN_PER_UNIT = 12;
    private static final int[] STAGE_POINT_THRESHOLDS = {100, 300, 600, 1000, 1500};
    private static final int[] STAGE_MASTER_VIRTUE = {10, 20, 35, 55, 80};
    private static final int[] STAGE_APPRENTICE_COIN = {20, 40, 70, 110, 160};

    public String createRelation(Character actor, String targetName) {
        if (actor == null || targetName == null || targetName.isBlank()) {
            return "请输入正确的角色名。";
        }

        try (Connection con = DatabaseConnection.getConnection()) {
            CharacterRecord target = loadCharacterByName(con, targetName.trim());
            if (target == null) {
                return "没有找到角色 #b" + targetName + "#k。";
            }
            CharacterRecord actorRecord = loadCharacterById(con, actor.getId());
            if (actorRecord == null) {
                return "当前角色数据不存在，请重新登录后再试。";
            }
            if (actorRecord.id == target.id) {
                return "不能和自己建立师徒关系。";
            }

            CharacterRecord master = actorRecord.level >= MASTER_MIN_LEVEL ? actorRecord : target;
            CharacterRecord apprentice = master.id == actorRecord.id ? target : actorRecord;
            Character targetOnline = findOnlineCharacterById(target.id);
            long actorPower = calculatePower(actor);
            long targetPower = targetOnline == null ? calculatePower(target) : calculatePower(targetOnline);
            long masterPower = master.id == actorRecord.id ? actorPower : targetPower;
            long apprenticePower = apprentice.id == actorRecord.id ? actorPower : targetPower;
            return createRelation(con, master, apprentice, masterPower, apprenticePower);
        } catch (SQLException e) {
            log.error("Failed to create mentorship relation for {} -> {}", actor.getName(), targetName, e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String getPartyMasterMenu(Character actor) {
        List<Character> members = getOnlinePartyMembers(actor);
        if (members.size() < 2) {
            return "请先和要建立师徒关系的角色组队。";
        }

        StringBuilder text = new StringBuilder("#e确认师傅#n\r\n\r\n请选择本队伍中的师傅：\r\n\r\n");
        int count = 0;
        for (Character member : members) {
            if (member.getLevel() >= MASTER_MIN_LEVEL) {
                text.append("#L").append(member.getId()).append("##b")
                        .append(member.getName()).append("#k  等级 ")
                        .append(member.getLevel()).append("#l\r\n");
                count++;
            }
        }
        if (count == 0) {
            return "队伍中没有达到 " + MASTER_MIN_LEVEL + " 级的师傅候选。";
        }
        text.append("\r\n选择后，队伍中其他符合条件的成员会作为徒弟建立关系。");
        return text.toString();
    }

    public boolean hasPartyMasterCandidate(Character actor) {
        for (Character member : getOnlinePartyMembers(actor)) {
            if (member.getLevel() >= MASTER_MIN_LEVEL) {
                return true;
            }
        }
        return false;
    }

    public String createRelationsFromParty(Character actor, int masterCid) {
        List<Character> members = getOnlinePartyMembers(actor);
        if (members.size() < 2) {
            return "请先和要建立师徒关系的角色组队。";
        }

        Character masterChr = null;
        for (Character member : members) {
            if (member.getId() == masterCid) {
                masterChr = member;
                break;
            }
        }
        if (masterChr == null) {
            return "选择的师傅不在当前在线队伍中。";
        }
        if (masterChr.getLevel() < MASTER_MIN_LEVEL) {
            return "师傅必须达到 " + MASTER_MIN_LEVEL + " 级以上。";
        }

        try (Connection con = DatabaseConnection.getConnection()) {
            CharacterRecord master = loadCharacterById(con, masterChr.getId());
            if (master == null) {
                return "师傅角色数据不存在，请重新登录后再试。";
            }

            long masterPower = calculatePower(masterChr);
            int success = 0;
            StringBuilder result = new StringBuilder("#e师徒关系建立结果#n\r\n\r\n");
            for (Character member : members) {
                if (member.getId() == masterChr.getId()) {
                    continue;
                }
                CharacterRecord apprentice = loadCharacterById(con, member.getId());
                if (apprentice == null) {
                    result.append(member.getName()).append("：角色数据不存在。\r\n");
                    continue;
                }
                String message = createRelation(con, master, apprentice, masterPower, calculatePower(member));
                if (message.startsWith("师徒关系建立成功")) {
                    success++;
                }
                result.append(member.getName()).append("：").append(message).append("\r\n");
            }

            if (success == 0) {
                result.append("\r\n没有成功建立新的师徒关系。");
            }
            return result.toString();
        } catch (SQLException e) {
            log.error("Failed to create mentorship relations from party for {}", actor.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String getOverview(Character chr) {
        if (chr == null) {
            return "角色不存在。";
        }
        finishExpiredDuels();
        checkAutoGraduation(chr);
        try (Connection con = DatabaseConnection.getConnection()) {
            Wallet wallet = ensureWallet(con, chr.getId());
            List<RelationRecord> relations = loadActiveRelations(con, chr.getId());
            int currentWeeklyPoints = loadCurrentWeeklyPoints(con, chr.getId());
            StringBuilder text = new StringBuilder("#e师徒系统#n\r\n\r\n");
            text.append("师徒币：#b").append(wallet.apprenticeCoin).append("#k\r\n");
            text.append("师德币：#b").append(wallet.virtueCoin).append("#k\r\n");
            text.append("累计积分：#b").append(wallet.totalPoints).append("#k，本周积分：#b").append(currentWeeklyPoints).append("#k\r\n\r\n");
            if (relations.isEmpty()) {
                text.append("当前没有进行中的师徒关系。\r\n");
            } else {
                for (RelationRecord relation : relations) {
                    boolean isMaster = relation.masterCid == chr.getId();
                    text.append(isMaster ? "师傅：" : "徒弟：")
                            .append("#b")
                            .append(isMaster ? relation.apprenticeName : relation.masterName)
                            .append("#k  积分：#r")
                            .append(relation.totalPoints)
                            .append("#k  阶段：")
                            .append(relation.rewardStep)
                            .append("/")
                            .append(STAGE_POINT_THRESHOLDS.length)
                            .append("\r\n");
                }
            }
            return text.toString();
        } catch (SQLException e) {
            log.error("Failed to build mentorship overview for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String cancelActiveRelation(Character chr) {
        if (chr == null) {
            return "角色不存在。";
        }
        try (Connection con = DatabaseConnection.getConnection();
             PreparedStatement ps = con.prepareStatement("""
                     UPDATE mentorship_relation
                     SET status = ?, graduate_time = CURRENT_TIMESTAMP
                     WHERE status = ? AND (master_cid = ? OR apprentice_cid = ?)
                     """)) {
            ps.setInt(1, STATUS_CANCELLED);
            ps.setInt(2, STATUS_ACTIVE);
            ps.setInt(3, chr.getId());
            ps.setInt(4, chr.getId());
            int rows = ps.executeUpdate();
            return rows > 0 ? "已解除当前进行中的师徒关系。" : "当前没有可解除的师徒关系。";
        } catch (SQLException e) {
            log.error("Failed to cancel mentorship relation for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String claimStageRewards(Character chr) {
        if (chr == null) {
            return "角色不存在。";
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            List<RelationRecord> relations = loadEarnedRelationsForUpdate(con, chr.getId());
            int masterVirtue = 0;
            int apprenticeCoin = 0;
            int claimedSteps = 0;
            for (RelationRecord relation : relations) {
                int nextStep = relation.rewardStep;
                int relationMasterVirtue = 0;
                int relationApprenticeCoin = 0;
                while (nextStep < STAGE_POINT_THRESHOLDS.length && relation.totalPoints >= STAGE_POINT_THRESHOLDS[nextStep]) {
                    if (insertRewardLog(con, relation.id, "stage_" + (nextStep + 1))) {
                        relationMasterVirtue += STAGE_MASTER_VIRTUE[nextStep];
                        relationApprenticeCoin += STAGE_APPRENTICE_COIN[nextStep];
                        claimedSteps++;
                    }
                    nextStep++;
                }
                if (nextStep != relation.rewardStep) {
                    updateRewardStep(con, relation.id, nextStep);
                }
                if (relationMasterVirtue > 0) {
                    addWallet(con, relation.masterCid, 0, relationMasterVirtue, 0);
                    masterVirtue += relationMasterVirtue;
                }
                if (relationApprenticeCoin > 0) {
                    addWallet(con, relation.apprenticeCid, relationApprenticeCoin, 0, 0);
                    apprenticeCoin += relationApprenticeCoin;
                }
            }
            if (claimedSteps == 0) {
                con.rollback();
                return "当前没有可领取的阶段奖励。";
            }
            con.commit();
            return "已领取阶段奖励：" + claimedSteps + " 阶，师傅获得师德币 " + masterVirtue + "，徒弟获得师徒币 " + apprenticeCoin + "。";
        } catch (SQLException e) {
            log.error("Failed to claim mentorship stage rewards for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String claimWeeklyPool(Character chr) {
        if (chr == null) {
            return "角色不存在。";
        }
        String weekKey = currentWeekKey();
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            List<RelationRecord> relations = loadEarnedRelationsForUpdate(con, chr.getId());
            int claimedPoints = 0;
            int gainedCoins = 0;
            int gainedVirtue = 0;
            int gainedApprentice = 0;
            for (RelationRecord relation : relations) {
                WeeklyPool pool = loadWeeklyPoolForUpdate(con, relation.id, weekKey);
                if (pool == null || pool.points <= 0) {
                    continue;
                }
                boolean isMaster = chr.getId() == relation.masterCid;
                boolean alreadyClaimed = isMaster ? pool.claimMaster > 0 : pool.claimApprentice > 0;
                if (alreadyClaimed) {
                    continue;
                }
                int units = Math.max(1, pool.points / WEEKLY_CLAIM_UNIT);
                int coins = isMaster ? units * WEEKLY_MASTER_VIRTUE_PER_UNIT : units * WEEKLY_APPRENTICE_COIN_PER_UNIT;
                markWeeklyClaimed(con, relation.id, weekKey, isMaster);
                addWallet(con, chr.getId(), isMaster ? 0 : coins, isMaster ? coins : 0, 0);
                claimedPoints += pool.points;
                gainedCoins += coins;
                if (isMaster) {
                    gainedVirtue += coins;
                } else {
                    gainedApprentice += coins;
                }
            }
            if (claimedPoints <= 0) {
                con.rollback();
                return "本周暂无可领取历练池奖励。";
            }
            con.commit();
            String rewardText = gainedVirtue > 0 && gainedApprentice > 0
                    ? "师德币 " + gainedVirtue + "、师徒币 " + gainedApprentice
                    : (gainedVirtue > 0 ? "师德币 " + gainedVirtue : "师徒币 " + gainedApprentice);
            return "已领取本周历练池 " + claimedPoints + " 积分奖励，获得 " + rewardText + "。";
        } catch (SQLException e) {
            log.error("Failed to claim mentorship weekly pool for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String startDuel(Character chr, int stake) {
        if (chr == null) {
            return "角色不存在。";
        }
        if (stake < MIN_DUEL_STAKE) {
            return "对决下注最少需要 " + MIN_DUEL_STAKE + " 枚师德币。";
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            RelationRecord relation = loadFirstActiveRelationForUpdate(con, chr.getId());
            if (relation == null) {
                con.rollback();
                return "需要先建立师徒关系，才能参加对决积分赛。";
            }
            if (hasOpenDuel(con, relation.id)) {
                con.rollback();
                return "你的师徒组合已经有进行中或排队中的对决。";
            }
            if (!spendVirtue(con, chr.getId(), stake)) {
                con.rollback();
                return "师德币不足，无法下注。";
            }
            try (PreparedStatement ps = con.prepareStatement("""
                    INSERT INTO mentorship_duel (relation_a, stake, status)
                    VALUES (?, ?, 0)
                    """)) {
                ps.setInt(1, relation.id);
                ps.setInt(2, stake);
                ps.executeUpdate();
            }
            con.commit();
            return "已报名 24 小时对决积分赛，等待另一组师徒加入。";
        } catch (SQLException e) {
            log.error("Failed to start mentorship duel for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String joinDuel(Character chr, int stakeLimit) {
        if (chr == null) {
            return "角色不存在。";
        }
        if (stakeLimit < MIN_DUEL_STAKE) {
            return "匹配下注上限最少需要 " + MIN_DUEL_STAKE + " 枚师德币。";
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            RelationRecord relation = loadFirstActiveRelationForUpdate(con, chr.getId());
            if (relation == null) {
                con.rollback();
                return "需要先建立师徒关系，才能参加对决积分赛。";
            }
            if (hasOpenDuel(con, relation.id)) {
                con.rollback();
                return "你的师徒组合已经有进行中或排队中的对决。";
            }
            DuelRecord duel = loadQueuedDuelForUpdate(con, relation.id, stakeLimit);
            if (duel == null) {
                con.rollback();
                return "暂时没有可匹配的对决队列。";
            }
            if (!spendVirtue(con, chr.getId(), duel.stake)) {
                con.rollback();
                return "师德币不足，无法匹配该下注对决。";
            }
            try (PreparedStatement ps = con.prepareStatement("""
                    UPDATE mentorship_duel
                    SET relation_b = ?, status = 1, started_at = CURRENT_TIMESTAMP, ends_at = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 24 HOUR)
                    WHERE id = ? AND status = 0
                    """)) {
                ps.setInt(1, relation.id);
                ps.setInt(2, duel.id);
                ps.executeUpdate();
            }
            con.commit();
            return "匹配成功，24 小时内获得的师徒积分会计入对决。";
        } catch (SQLException e) {
            log.error("Failed to join mentorship duel for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String getDuelStatus(Character chr) {
        if (chr == null) {
            return "角色不存在。";
        }
        finishExpiredDuels();
        try (Connection con = DatabaseConnection.getConnection();
             PreparedStatement ps = con.prepareStatement("""
                     SELECT d.*
                     FROM mentorship_duel d
                     JOIN mentorship_relation r ON r.id IN (d.relation_a, d.relation_b)
                     WHERE (r.master_cid = ? OR r.apprentice_cid = ?) AND d.status IN (0, 1)
                     ORDER BY d.id DESC
                     LIMIT 1
                     """)) {
            ps.setInt(1, chr.getId());
            ps.setInt(2, chr.getId());
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    return "当前没有排队中或进行中的对决。";
                }
                int status = rs.getInt("status");
                String state = status == 0 ? "排队中" : "进行中";
                return "对决状态：" + state + "\r\nA 组积分：" + rs.getInt("points_a")
                        + "\r\nB 组积分：" + rs.getInt("points_b")
                        + "\r\n下注：" + rs.getInt("stake") + " 师德币";
            }
        } catch (SQLException e) {
            log.error("Failed to query mentorship duel status for {}", chr.getId(), e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public String getRankingText(String type) {
        boolean weekly = "weekly".equalsIgnoreCase(type);
        String title = weekly ? "本周师徒榜" : "累计师徒榜";
        String sql = weekly ? """
                SELECT CONCAT(r.master_name, ' / ', r.apprentice_name) AS names, p.points AS points
                FROM mentorship_weekly_pool p
                JOIN mentorship_relation r ON r.id = p.relationid
                WHERE p.week_key = ? AND r.status IN (?, ?) AND p.points > 0
                ORDER BY p.points DESC, r.id ASC
                LIMIT 10
                """ : """
                SELECT CONCAT(master_name, ' / ', apprentice_name) AS names, total_points AS points
                FROM mentorship_relation
                WHERE status IN (?, ?) AND total_points > 0
                ORDER BY total_points DESC, id ASC
                LIMIT 10
                """;
        try (Connection con = DatabaseConnection.getConnection();
             PreparedStatement ps = con.prepareStatement(sql)) {
            if (weekly) {
                ps.setString(1, currentWeekKey());
                ps.setInt(2, STATUS_ACTIVE);
                ps.setInt(3, STATUS_GRADUATED);
            } else {
                ps.setInt(1, STATUS_ACTIVE);
                ps.setInt(2, STATUS_GRADUATED);
            }
            StringBuilder text = new StringBuilder("#e").append(title).append("#n\r\n\r\n");
            try (ResultSet rs = ps.executeQuery()) {
                int rank = 1;
                while (rs.next()) {
                    text.append(rank++).append(". #b").append(rs.getString("names")).append("#k  ")
                            .append(rs.getInt("points")).append("\r\n");
                }
                if (rank == 1) {
                    text.append("暂无排行数据。");
                }
            }
            return text.toString();
        } catch (SQLException e) {
            log.error("Failed to query mentorship ranking {}", type, e);
            return "师徒系统暂时不可用，请稍后再试。";
        }
    }

    public boolean spendVirtueCoins(Character chr, int cost) {
        if (chr == null || cost <= 0) {
            return false;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            return spendVirtue(con, chr.getId(), cost);
        } catch (SQLException e) {
            log.error("Failed to spend virtue coins for {}", chr.getId(), e);
            return false;
        }
    }

    public boolean spendApprenticeCoins(Character chr, int cost) {
        if (chr == null || cost <= 0) {
            return false;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            return spendApprentice(con, chr.getId(), cost);
        } catch (SQLException e) {
            log.error("Failed to spend apprentice coins for {}", chr.getId(), e);
            return false;
        }
    }

    public int getVirtueCoins(Character chr) {
        if (chr == null) {
            return 0;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            return ensureWallet(con, chr.getId()).virtueCoin;
        } catch (SQLException e) {
            log.error("Failed to get virtue coins for {}", chr.getId(), e);
            return 0;
        }
    }

    public int getApprenticeCoins(Character chr) {
        if (chr == null) {
            return 0;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            return ensureWallet(con, chr.getId()).apprenticeCoin;
        } catch (SQLException e) {
            log.error("Failed to get apprentice coins for {}", chr.getId(), e);
            return 0;
        }
    }

    public void recordGpqClear(Collection<Character> players) {
        if (players == null || players.isEmpty()) {
            return;
        }
        Set<Integer> characterIds = new HashSet<>();
        for (Character player : players) {
            if (player != null) {
                characterIds.add(player.getId());
            }
        }
        if (characterIds.isEmpty()) {
            return;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            String eventKey = "gpq:" + System.currentTimeMillis() + ":" + characterIds.hashCode();
            List<RelationRecord> relations = loadActiveRelationsByParticipants(con, characterIds);
            for (RelationRecord relation : relations) {
                addPoints(con, relation, GPQ_CLEAR_POINTS, eventKey);
            }
            con.commit();
        } catch (SQLException e) {
            log.error("Failed to record GPQ mentorship clear", e);
        }
    }

    public void checkAutoGraduation(Character chr) {
        if (chr == null) {
            return;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            List<RelationRecord> relations = loadActiveRelationsForUpdate(con, chr.getId());
            long currentPower = calculatePower(chr);
            for (RelationRecord relation : relations) {
                long masterPower = relation.masterCid == chr.getId() ? currentPower : relation.lastMasterPower;
                long apprenticePower = relation.apprenticeCid == chr.getId() ? currentPower : relation.lastApprenticePower;
                updateLastPower(con, relation.id, masterPower, apprenticePower);
                if (apprenticePower > masterPower && masterPower > 0) {
                    graduate(con, relation.id);
                    addWallet(con, relation.masterCid, 0, 50, 0);
                    addWallet(con, relation.apprenticeCid, 100, 0, 0);
                    notifyGraduation(chr, relation, apprenticePower, masterPower);
                }
            }
            con.commit();
        } catch (SQLException e) {
            log.error("Failed to check mentorship auto graduation for {}", chr.getId(), e);
        }
    }

    private String createRelation(Connection con, CharacterRecord master, CharacterRecord apprentice, long masterPower, long apprenticePower) throws SQLException {
        if (master.level < MASTER_MIN_LEVEL) {
            return "师傅必须达到 " + MASTER_MIN_LEVEL + " 级以上。点券会参与战力计算，但不能绕过等级条件。";
        }
        if (apprentice.reborns != 0) {
            return "徒弟必须是未转生角色。";
        }
        if (master.guildId <= 0 || master.guildId != apprentice.guildId) {
            return "师傅和徒弟必须在同一个家族。";
        }
        if (hasActiveRelation(con, apprentice.id)) {
            return "该徒弟已经有进行中的师徒关系。";
        }

        try (PreparedStatement ps = con.prepareStatement("""
                INSERT INTO mentorship_relation
                (master_cid, master_accountid, master_name, apprentice_cid, apprentice_accountid, apprentice_name,
                 guildid, start_master_power, start_apprentice_power, last_master_power, last_apprentice_power)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """)) {
            ps.setInt(1, master.id);
            ps.setInt(2, master.accountId);
            ps.setString(3, master.name);
            ps.setInt(4, apprentice.id);
            ps.setInt(5, apprentice.accountId);
            ps.setString(6, apprentice.name);
            ps.setInt(7, master.guildId);
            ps.setLong(8, masterPower);
            ps.setLong(9, apprenticePower);
            ps.setLong(10, masterPower);
            ps.setLong(11, apprenticePower);
            ps.executeUpdate();
        }
        ensureWallet(con, master.id);
        ensureWallet(con, apprentice.id);
        return "师徒关系建立成功：#b" + master.name + "#k 收 #b" + apprentice.name + "#k 为徒。";
    }

    private void addPoints(Connection con, RelationRecord relation, int points, String eventKey) throws SQLException {
        if (!insertEventLog(con, eventKey, relation.id, points)) {
            return;
        }
        String weekKey = currentWeekKey();
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_relation
                SET total_points = total_points + ?
                WHERE id = ? AND status = ?
                """)) {
            ps.setInt(1, points);
            ps.setInt(2, relation.id);
            ps.setInt(3, STATUS_ACTIVE);
            ps.executeUpdate();
        }
        upsertWeeklyPool(con, relation.id, weekKey, points);
        addWallet(con, relation.masterCid, 0, points / 10, points);
        addWallet(con, relation.apprenticeCid, points / 5, 0, points);
        addDuelPoints(con, relation.id, points);
    }

    private boolean insertEventLog(Connection con, String eventKey, int relationId, int points) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                INSERT IGNORE INTO mentorship_event_log (event_key, relationid, points)
                VALUES (?, ?, ?)
                """)) {
            ps.setString(1, eventKey);
            ps.setInt(2, relationId);
            ps.setInt(3, points);
            return ps.executeUpdate() > 0;
        }
    }

    private boolean insertRewardLog(Connection con, int relationId, String rewardKey) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                INSERT IGNORE INTO mentorship_reward_log (relationid, reward_key)
                VALUES (?, ?)
                """)) {
            ps.setInt(1, relationId);
            ps.setString(2, rewardKey);
            return ps.executeUpdate() > 0;
        }
    }

    private Wallet ensureWallet(Connection con, int characterId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                INSERT IGNORE INTO mentorship_wallet (characterid)
                VALUES (?)
                """)) {
            ps.setInt(1, characterId);
            ps.executeUpdate();
        }
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT apprentice_coin, virtue_coin, total_points, weekly_points
                FROM mentorship_wallet
                WHERE characterid = ?
                """)) {
            ps.setInt(1, characterId);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return new Wallet(rs.getInt("apprentice_coin"), rs.getInt("virtue_coin"), rs.getInt("total_points"), rs.getInt("weekly_points"));
                }
            }
        }
        return new Wallet(0, 0, 0, 0);
    }

    private void addWallet(Connection con, int characterId, int apprenticeCoin, int virtueCoin, int points) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                INSERT INTO mentorship_wallet (characterid, apprentice_coin, virtue_coin, total_points, weekly_points)
                VALUES (?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    apprentice_coin = apprentice_coin + VALUES(apprentice_coin),
                    virtue_coin = virtue_coin + VALUES(virtue_coin),
                    total_points = total_points + VALUES(total_points),
                    weekly_points = weekly_points + VALUES(weekly_points)
                """)) {
            ps.setInt(1, characterId);
            ps.setInt(2, apprenticeCoin);
            ps.setInt(3, virtueCoin);
            ps.setInt(4, points);
            ps.setInt(5, points);
            ps.executeUpdate();
        }
    }

    private boolean spendVirtue(Connection con, int characterId, int cost) throws SQLException {
        ensureWallet(con, characterId);
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_wallet
                SET virtue_coin = virtue_coin - ?
                WHERE characterid = ? AND virtue_coin >= ?
                """)) {
            ps.setInt(1, cost);
            ps.setInt(2, characterId);
            ps.setInt(3, cost);
            return ps.executeUpdate() > 0;
        }
    }

    private boolean spendApprentice(Connection con, int characterId, int cost) throws SQLException {
        ensureWallet(con, characterId);
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_wallet
                SET apprentice_coin = apprentice_coin - ?
                WHERE characterid = ? AND apprentice_coin >= ?
                """)) {
            ps.setInt(1, cost);
            ps.setInt(2, characterId);
            ps.setInt(3, cost);
            return ps.executeUpdate() > 0;
        }
    }

    private void upsertWeeklyPool(Connection con, int relationId, String weekKey, int points) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                INSERT INTO mentorship_weekly_pool (relationid, week_key, points)
                VALUES (?, ?, ?)
                ON DUPLICATE KEY UPDATE points = points + VALUES(points)
                """)) {
            ps.setInt(1, relationId);
            ps.setString(2, weekKey);
            ps.setInt(3, points);
            ps.executeUpdate();
        }
    }

    private void markWeeklyClaimed(Connection con, int relationId, String weekKey, boolean master) throws SQLException {
        String column = master ? "claim_master" : "claim_apprentice";
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_weekly_pool
                SET %s = 1
                WHERE relationid = ? AND week_key = ?
                """.formatted(column))) {
            ps.setInt(1, relationId);
            ps.setString(2, weekKey);
            ps.executeUpdate();
        }
    }

    private WeeklyPool loadWeeklyPoolForUpdate(Connection con, int relationId, String weekKey) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT points, claim_master, claim_apprentice
                FROM mentorship_weekly_pool
                WHERE relationid = ? AND week_key = ?
                FOR UPDATE
                """)) {
            ps.setInt(1, relationId);
            ps.setString(2, weekKey);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return new WeeklyPool(rs.getInt("points"), rs.getInt("claim_master"), rs.getInt("claim_apprentice"));
                }
            }
        }
        return null;
    }

    private void addDuelPoints(Connection con, int relationId, int points) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_duel
                SET points_a = points_a + CASE WHEN relation_a = ? THEN ? ELSE 0 END,
                    points_b = points_b + CASE WHEN relation_b = ? THEN ? ELSE 0 END
                WHERE status = 1 AND ends_at > CURRENT_TIMESTAMP AND (relation_a = ? OR relation_b = ?)
                """)) {
            ps.setInt(1, relationId);
            ps.setInt(2, points);
            ps.setInt(3, relationId);
            ps.setInt(4, points);
            ps.setInt(5, relationId);
            ps.setInt(6, relationId);
            ps.executeUpdate();
        }
    }

    private void finishExpiredDuels() {
        try (Connection con = DatabaseConnection.getConnection()) {
            con.setAutoCommit(false);
            try (PreparedStatement ps = con.prepareStatement("""
                    SELECT id, relation_a, relation_b, stake, points_a, points_b
                    FROM mentorship_duel
                    WHERE status = 1 AND ends_at <= CURRENT_TIMESTAMP
                    FOR UPDATE
                    """);
                 ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    int id = rs.getInt("id");
                    int winner = rs.getInt("points_a") >= rs.getInt("points_b") ? rs.getInt("relation_a") : rs.getInt("relation_b");
                    int stake = rs.getInt("stake");
                    int masterCid = loadRelationMaster(con, winner);
                    if (stake > 0 && masterCid > 0) {
                        addWallet(con, masterCid, 0, stake * 2, 0);
                    }
                    try (PreparedStatement upd = con.prepareStatement("""
                            UPDATE mentorship_duel
                            SET status = 2, winner_relation = ?, finished_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """)) {
                        upd.setInt(1, winner);
                        upd.setInt(2, id);
                        upd.executeUpdate();
                    }
                }
            }
            con.commit();
        } catch (SQLException e) {
            log.error("Failed to finish expired mentorship duels", e);
        }
    }

    private int loadRelationMaster(Connection con, int relationId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("SELECT master_cid FROM mentorship_relation WHERE id = ?")) {
            ps.setInt(1, relationId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? rs.getInt("master_cid") : 0;
            }
        }
    }

    private DuelRecord loadQueuedDuelForUpdate(Connection con, int relationId, int stakeLimit) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT id, stake
                FROM mentorship_duel
                WHERE status = 0 AND relation_a <> ? AND stake >= ? AND stake <= ?
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE
                """)) {
            ps.setInt(1, relationId);
            ps.setInt(2, MIN_DUEL_STAKE);
            ps.setInt(3, stakeLimit);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return new DuelRecord(rs.getInt("id"), rs.getInt("stake"));
                }
            }
        }
        return null;
    }

    private boolean hasOpenDuel(Connection con, int relationId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT 1
                FROM mentorship_duel
                WHERE status IN (0, 1) AND (relation_a = ? OR relation_b = ?)
                LIMIT 1
                """)) {
            ps.setInt(1, relationId);
            ps.setInt(2, relationId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        }
    }

    private void updateRewardStep(Connection con, int relationId, int step) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("UPDATE mentorship_relation SET reward_step = ? WHERE id = ?")) {
            ps.setInt(1, step);
            ps.setInt(2, relationId);
            ps.executeUpdate();
        }
    }

    private void updateLastPower(Connection con, int relationId, long masterPower, long apprenticePower) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_relation
                SET last_master_power = ?, last_apprentice_power = ?
                WHERE id = ?
                """)) {
            ps.setLong(1, masterPower);
            ps.setLong(2, apprenticePower);
            ps.setInt(3, relationId);
            ps.executeUpdate();
        }
    }

    private void graduate(Connection con, int relationId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                UPDATE mentorship_relation
                SET status = ?, graduate_time = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
                """)) {
            ps.setInt(1, STATUS_GRADUATED);
            ps.setInt(2, relationId);
            ps.setInt(3, STATUS_ACTIVE);
            ps.executeUpdate();
        }
    }

    private void notifyGraduation(Character trigger, RelationRecord relation, long apprenticePower, long masterPower) {
        String text = "[师徒] 徒弟 " + relation.apprenticeName + " 战力 " + apprenticePower
                + " 已超过师傅 " + relation.masterName + " 战力 " + masterPower + "，自动出师。";
        trigger.dropMessage(5, text);
    }

    private boolean hasActiveRelation(Connection con, int apprenticeId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT 1 FROM mentorship_relation
                WHERE apprentice_cid = ? AND status = ?
                LIMIT 1
                """)) {
            ps.setInt(1, apprenticeId);
            ps.setInt(2, STATUS_ACTIVE);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        }
    }

    private RelationRecord loadFirstActiveRelationForUpdate(Connection con, int characterId) throws SQLException {
        List<RelationRecord> relations = loadActiveRelationsForUpdate(con, characterId);
        return relations.isEmpty() ? null : relations.get(0);
    }

    private List<RelationRecord> loadActiveRelations(Connection con, int characterId) throws SQLException {
        return loadRelations(con, """
                SELECT * FROM mentorship_relation
                WHERE status = ? AND (master_cid = ? OR apprentice_cid = ?)
                ORDER BY id
                """, characterId);
    }

    private List<RelationRecord> loadActiveRelationsForUpdate(Connection con, int characterId) throws SQLException {
        return loadRelations(con, """
                SELECT * FROM mentorship_relation
                WHERE status = ? AND (master_cid = ? OR apprentice_cid = ?)
                ORDER BY id
                FOR UPDATE
                """, characterId);
    }

    private List<RelationRecord> loadEarnedRelationsForUpdate(Connection con, int characterId) throws SQLException {
        List<RelationRecord> relations = new ArrayList<>();
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT * FROM mentorship_relation
                WHERE status IN (?, ?) AND (master_cid = ? OR apprentice_cid = ?)
                ORDER BY id
                FOR UPDATE
                """)) {
            ps.setInt(1, STATUS_ACTIVE);
            ps.setInt(2, STATUS_GRADUATED);
            ps.setInt(3, characterId);
            ps.setInt(4, characterId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    relations.add(readRelation(rs));
                }
            }
        }
        return relations;
    }

    private List<RelationRecord> loadRelations(Connection con, String sql, int characterId) throws SQLException {
        List<RelationRecord> relations = new ArrayList<>();
        try (PreparedStatement ps = con.prepareStatement(sql)) {
            ps.setInt(1, STATUS_ACTIVE);
            ps.setInt(2, characterId);
            ps.setInt(3, characterId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    relations.add(readRelation(rs));
                }
            }
        }
        return relations;
    }

    private List<RelationRecord> loadActiveRelationsByParticipants(Connection con, Set<Integer> characterIds) throws SQLException {
        List<RelationRecord> relations = new ArrayList<>();
        String placeholders = String.join(",", Collections.nCopies(characterIds.size(), "?"));
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT DISTINCT *
                FROM mentorship_relation
                WHERE status = ? AND (master_cid IN (%s) OR apprentice_cid IN (%s))
                """.formatted(placeholders, placeholders))) {
            int index = 1;
            ps.setInt(index++, STATUS_ACTIVE);
            for (int cid : characterIds) {
                ps.setInt(index++, cid);
            }
            for (int cid : characterIds) {
                ps.setInt(index++, cid);
            }
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    relations.add(readRelation(rs));
                }
            }
        }
        return relations;
    }

    private int loadCurrentWeeklyPoints(Connection con, int characterId) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT COALESCE(SUM(p.points), 0) AS points
                FROM mentorship_weekly_pool p
                JOIN mentorship_relation r ON r.id = p.relationid
                WHERE p.week_key = ? AND r.status IN (?, ?) AND (r.master_cid = ? OR r.apprentice_cid = ?)
                """)) {
            ps.setString(1, currentWeekKey());
            ps.setInt(2, STATUS_ACTIVE);
            ps.setInt(3, STATUS_GRADUATED);
            ps.setInt(4, characterId);
            ps.setInt(5, characterId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? rs.getInt("points") : 0;
            }
        }
    }

    private RelationRecord readRelation(ResultSet rs) throws SQLException {
        return new RelationRecord(
                rs.getInt("id"),
                rs.getInt("master_cid"),
                rs.getString("master_name"),
                rs.getInt("apprentice_cid"),
                rs.getString("apprentice_name"),
                rs.getInt("total_points"),
                rs.getInt("reward_step"),
                rs.getLong("last_master_power"),
                rs.getLong("last_apprentice_power")
        );
    }

    private CharacterRecord loadCharacterByName(Connection con, String name) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT c.id, c.accountid, c.name, c.level, c.guildid, c.reborns,
                       c.`str`, c.dex, c.`int`, c.luk, c.maxhp, c.maxmp,
                       a.nxCredit, a.maplePoint, a.nxPrepaid
                FROM characters c
                JOIN accounts a ON a.id = c.accountid
                WHERE c.name = ?
                """)) {
            ps.setString(1, name);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? readCharacter(rs) : null;
            }
        }
    }

    private CharacterRecord loadCharacterById(Connection con, int id) throws SQLException {
        try (PreparedStatement ps = con.prepareStatement("""
                SELECT c.id, c.accountid, c.name, c.level, c.guildid, c.reborns,
                       c.`str`, c.dex, c.`int`, c.luk, c.maxhp, c.maxmp,
                       a.nxCredit, a.maplePoint, a.nxPrepaid
                FROM characters c
                JOIN accounts a ON a.id = c.accountid
                WHERE c.id = ?
                """)) {
            ps.setInt(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? readCharacter(rs) : null;
            }
        }
    }

    private CharacterRecord readCharacter(ResultSet rs) throws SQLException {
        return new CharacterRecord(
                rs.getInt("id"),
                rs.getInt("accountid"),
                rs.getString("name"),
                rs.getInt("level"),
                rs.getInt("guildid"),
                rs.getInt("reborns"),
                rs.getInt("str"),
                rs.getInt("dex"),
                rs.getInt("int"),
                rs.getInt("luk"),
                rs.getInt("maxhp"),
                rs.getInt("maxmp"),
                rs.getInt("nxCredit"),
                rs.getInt("maplePoint"),
                rs.getInt("nxPrepaid")
        );
    }

    public long calculatePower(Character chr) {
        if (chr == null) {
            return 0L;
        }
        long cashPower = 0L;
        if (chr.getCashShop() != null) {
            cashPower += Math.max(0, chr.getCashShop().getCash(CashShop.NX_CREDIT));
            cashPower += Math.max(0, chr.getCashShop().getCash(CashShop.MAPLE_POINT));
            cashPower += Math.max(0, chr.getCashShop().getCash(CashShop.NX_PREPAID));
        }
        long stats = chr.getTotalStr() + chr.getTotalDex() + chr.getTotalInt() + chr.getTotalLuk();
        long attack = Math.max(chr.getTotalWatk(), chr.getTotalMagic());
        return stats * Math.max(1L, attack)
                + chr.getCurrentMaxHp() / 10L
                + chr.getCurrentMaxMp() / 20L
                + cashPower / 100L;
    }

    private long calculatePower(CharacterRecord chr) {
        long cashPower = Math.max(0, chr.nxCredit) + Math.max(0, chr.maplePoint) + Math.max(0, chr.nxPrepaid);
        return chr.level * 1000L
                + chr.str * 10L + chr.dex * 10L + chr.intStat * 10L + chr.luk * 10L
                + chr.maxHp / 2L + chr.maxMp / 2L
                + cashPower / 100L;
    }

    private Character findOnlineCharacterById(int characterId) {
        return Server.getInstance().getWorlds().stream()
                .map(world -> world.getPlayerStorage().getCharacterById(characterId))
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    private List<Character> getOnlinePartyMembers(Character actor) {
        if (actor == null || actor.getParty() == null) {
            return Collections.emptyList();
        }
        return actor.getPartyMembersOnline();
    }

    private static String currentWeekKey() {
        LocalDate now = LocalDate.now();
        WeekFields weekFields = WeekFields.ISO;
        return String.format("%04dW%02d", now.get(weekFields.weekBasedYear()), now.get(weekFields.weekOfWeekBasedYear()));
    }

    private record CharacterRecord(int id, int accountId, String name, int level, int guildId, int reborns,
                                   int str, int dex, int intStat, int luk, int maxHp, int maxMp,
                                   int nxCredit, int maplePoint, int nxPrepaid) {
    }

    private record RelationRecord(int id, int masterCid, String masterName, int apprenticeCid, String apprenticeName,
                                  int totalPoints, int rewardStep, long lastMasterPower, long lastApprenticePower) {
    }

    private record Wallet(int apprenticeCoin, int virtueCoin, int totalPoints, int weeklyPoints) {
    }

    private record WeeklyPool(int points, int claimMaster, int claimApprentice) {
    }

    private record DuelRecord(int id, int stake) {
    }
}
