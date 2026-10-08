/*
    This file is part of the HeavenMS MapleStory Server
    Copyleft (L) 2016 - 2019 RonanLana

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
package org.gms.net.server.coordinator.session;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.config.GameConfig;
import org.gms.constants.id.NpcId;
import org.gms.net.server.Server;
import org.gms.net.server.coordinator.login.LoginStorage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.gms.util.DatabaseConnection;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.Instant;
import java.util.*;
import java.util.Map.Entry;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * @author Ronan
 */
public class SessionCoordinator {
    private static final Logger log = LoggerFactory.getLogger(SessionCoordinator.class);
    private static final SessionCoordinator instance = new SessionCoordinator();
    // 新增：记录每个用户（IP+HWID）当前登录的账号ID集合
    public Map<String, Set<Integer>> userAccountMap = new ConcurrentHashMap<>();

    public static SessionCoordinator getInstance() {
        return instance;
    }

    public enum AntiMulticlientResult {
        SUCCESS,
        REMOTE_LOGGEDIN,
        REMOTE_REACHED_LIMIT,
        REMOTE_PROCESSING,
        REMOTE_NO_MATCH,
        MANY_ACCOUNT_ATTEMPTS,
        COORDINATOR_ERROR
    }

    private final SessionInitialization sessionInit = new SessionInitialization();
    private final LoginStorage loginStorage = new LoginStorage();
    private final Map<Integer, Client> onlineClients = new HashMap<>(); // Key: account id
    private final Set<Hwid> onlineRemoteHwids = new HashSet<>(); // Hwid/nibblehwid
    private final Map<String, Client> loginRemoteHosts = new ConcurrentHashMap<>(); // Key: Ip (+ nibblehwid)
    private final HostHwidCache hostHwidCache = new HostHwidCache();

    private SessionCoordinator() {
    }

    private static boolean attemptAccountAccess(int accountId, Hwid hwid, boolean routineCheck) {
        try (Connection con = DatabaseConnection.getConnection()) {
            List<HwidRelevance> hwidRelevances = SessionDAO.getHwidRelevance(con, accountId);
            for (HwidRelevance hwidRelevance : hwidRelevances) {
                if (hwidRelevance.hwid().endsWith(hwid.hwid())) {
                    if (!routineCheck) {
                        // better update HWID relevance as soon as the login is authenticated
                        Instant expiry = HwidAssociationExpiry.getHwidAccountExpiry(hwidRelevance.relevance());
                        SessionDAO.updateAccountAccess(con, hwid, accountId, expiry, hwidRelevance.getIncrementedRelevance());
                    }

                    return true;
                }
            }

            if (hwidRelevances.size() < GameConfig.getServerInt("max_allowed_account_hwid")) {
                return true;
            }
        } catch (SQLException e) {
            log.warn("Failed to update account access. Account id: {}, nibbleHwid: {}", accountId, hwid, e);
        }

        return false;
    }

    public static String getSessionRemoteHost(Client client) {
        Hwid hwid = client.getHwid();

        if (hwid != null) {
            return client.getRemoteAddress() + "-" + hwid.hwid();
        } else {
            return client.getRemoteAddress();
        }
    }

    /**
     * Overwrites any existing online client for the account id, making sure to disconnect it as well.
     */
    public void updateOnlineClient(Client client) {
        if (client != null) {
            int accountId = client.getAccID();
            disconnectClientIfOnline(accountId);
            onlineClients.put(accountId, client);
        }
    }

    private void disconnectClientIfOnline(int accountId) {
        Client ingameClient = onlineClients.get(accountId);
        if (ingameClient != null) {     // thanks MedicOP for finding out a loss of loggedin account uniqueness when using the CMS "Unstuck" feature
            ingameClient.forceDisconnect();
        }
    }

    public boolean canStartLoginSession(Client client) {
        if (!GameConfig.getServerBoolean("deterred_multi_client")) {
            return true;
        }

        String remoteHost = getSessionRemoteHost(client);
        final InitializationResult initResult = sessionInit.initialize(remoteHost);
        switch (initResult.getAntiMulticlientResult()) {
            case REMOTE_PROCESSING -> {
                return false;
            }
            case COORDINATOR_ERROR -> {
                return true;
            }
        }

        try {
            final HostHwid knownHwid = hostHwidCache.getEntry(remoteHost);
            // 只检查HWID是否已在线，不再限制同一IP的登录会话数量
            if (knownHwid != null && onlineRemoteHwids.contains(knownHwid.hwid())) {
                return false;
            }

            loginRemoteHosts.put(remoteHost, client);
            return true;
        } finally {
            sessionInit.finalize(remoteHost);
        }
    }

    public void closeLoginSession(Client client) {
        clearLoginRemoteHost(client);

        Hwid nibbleHwid = client.getHwid();
        client.setHwid(null);
        if (nibbleHwid != null) {
            onlineRemoteHwids.remove(nibbleHwid);

            if (client != null) {
                Client loggedClient = onlineClients.get(client.getAccID());

                // do not remove an online game session here, only login session
                if (loggedClient != null && loggedClient.getSessionId() == client.getSessionId()) {
                    onlineClients.remove(client.getAccID());
                }
            }
        }
    }

    private void clearLoginRemoteHost(Client client) {
        String remoteHost = getSessionRemoteHost(client);
        loginRemoteHosts.remove(client.getRemoteAddress());
        loginRemoteHosts.remove(remoteHost);
    }

    public AntiMulticlientResult attemptLoginSession(Client client, Hwid hwid, int accountId, boolean routineCheck) {
        String remoteHost = getSessionRemoteHost(client);
        String realIp = getRealIp(remoteHost);
        log.info("【登录会话】开始处理登录 IP: {}, 账号ID: {}", realIp, accountId);
        
        try {
            // 校验多开（管理员账号ID=1跳过检查）
            if (accountId != 1 && isMultiOpen(remoteHost)) {
                log.warn("【登录会话】账号ID: {} 登录被拒绝，多开超限", accountId);
                return AntiMulticlientResult.REMOTE_REACHED_LIMIT; // 超过限制，拒绝登录
            }
            InitializationResult initResult = sessionInit.initialize(remoteHost);
            if (initResult != InitializationResult.SUCCESS) {
                return initResult.getAntiMulticlientResult();
            }
//            else if (!loginStorage.registerLogin(accountId)) {
//                return AntiMulticlientResult.MANY_ACCOUNT_ATTEMPTS;
//            } else if (routineCheck && !attemptAccountAccess(accountId, hwid, routineCheck)) {
//                return AntiMulticlientResult.REMOTE_REACHED_LIMIT;
//            } else if (onlineRemoteHwids.contains(hwid)) {
//                return AntiMulticlientResult.REMOTE_LOGGEDIN;
//            } else if (!attemptAccountAccess(accountId, hwid, routineCheck)) {
//                return AntiMulticlientResult.REMOTE_REACHED_LIMIT;
//            }
            cacheMultiOpenId(client, accountId);
            client.setHwid(hwid);
            onlineRemoteHwids.add(hwid);

            return AntiMulticlientResult.SUCCESS;
        } finally {
            sessionInit.finalize(remoteHost);
        }
    }

    public void cacheMultiOpenId(Client client, int accountId) {
        String remoteHost = getSessionRemoteHost(client);
        String realIp = getRealIp(remoteHost);
        // 记录当前账号到用户的登录列表中
        Set<Integer> accountSet = userAccountMap.computeIfAbsent(realIp, k -> ConcurrentHashMap.newKeySet());
        // 若accountId不在集合中，则添加
        if (!accountSet.contains(accountId)) {
            accountSet.add(accountId);
            log.info("【多开记录】IP: {}, 账号ID: {} 已添加到多开列表，当前该IP下账号数: {}", realIp, accountId, accountSet.size());
        } else {
            log.warn("【多开记录】IP: {}, 账号ID: {} 已在列表中，跳过添加", realIp, accountId);
        }
    }

    /**
     * 校验多开
     */
    public boolean isMultiOpen(String remoteHost) {
        try {
            String ip = getRealIp(remoteHost);
            int maxAllowed = GameConfig.getServerInt("max_accounts_per_user");
            
            log.info("【多开校验】开始校验 IP: {}, 配置的最大多开数: {}", ip, maxAllowed);
            
            // 检查是否启用了多开限制
            if (maxAllowed <= 0) {
                log.info("【多开校验】多开限制未启用 (max_accounts_per_user <= 0)，跳过校验");
                return false;
            }
            
            // 检查IP是否在白名单中
            String whiteIp = GameConfig.getServerString("multi_open_whitelist_ip");
            log.info("【多开校验】白名单IP: {}", whiteIp);
            
            if (ip != null && ip.equals(whiteIp)) {
                log.info("【多开校验】IP: {} 在白名单中，跳过多开校验", ip);
                return false;
            }
            
            // 检查该IP下已登录的账号数量
            Set<Integer> existingAccounts = userAccountMap.getOrDefault(ip, Collections.emptySet());
            log.info("【多开校验】IP: {} 当前已登录账号数: {}, 允许的最大数: {}", ip, existingAccounts.size(), maxAllowed);
            
            if (existingAccounts.size() >= maxAllowed) {
                log.warn("【多开校验】IP: {} 多开超过最大限制！已开启: {} 个, 限制: {} 个", 
                         ip, existingAccounts.size(), maxAllowed);
                return true;
            } else {
                log.info("【多开校验】IP: {} 多开检查通过，可继续登录", ip);
            }
        } catch (Exception e) {
            log.error("【多开校验】校验时发生异常: ", e);
        }
        return false;
    }

    /**
     * 从拼接的远程主机字符串中提取真实IP地址
     *
     * @param remoteHost 格式示例：192.168.1.1-8080、10.0.0.1、null、""
     * @return 提取的纯IP地址（空/异常场景返回空字符串，避免NPE）
     */
    public String getRealIp(String remoteHost) {
        if (remoteHost == null || remoteHost.trim().isEmpty()) {
            return "";
        }
        String cleanHost = remoteHost.trim();
        String[] parts = cleanHost.split("-", 2);
        String realIp = parts[0].trim();
        return realIp.isEmpty() ? "" : realIp;
    }

    public AntiMulticlientResult attemptGameSession(Client client, int accountId, Hwid hwid) {
        final String remoteHost = getSessionRemoteHost(client);
        if (!GameConfig.getServerBoolean("deterred_multi_client")) {
            hostHwidCache.addEntry(remoteHost, hwid);
            hostHwidCache.addEntry(client.getRemoteAddress(), hwid); // no HWID information on the loggedin newcomer session...
            return AntiMulticlientResult.SUCCESS;
        }

        final InitializationResult initResult = sessionInit.initialize(remoteHost);
        if (initResult != InitializationResult.SUCCESS) {
            return initResult.getAntiMulticlientResult();
        }

        try {
            Hwid clientHwid = client.getHwid(); // thanks Paxum for noticing account stuck after PIC failure
            if (clientHwid == null) {
                return AntiMulticlientResult.REMOTE_NO_MATCH;
            }

            onlineRemoteHwids.remove(clientHwid);

            if (!hwid.equals(clientHwid)) {
                return AntiMulticlientResult.REMOTE_NO_MATCH;
            } else if (onlineRemoteHwids.contains(hwid)) {
                return AntiMulticlientResult.REMOTE_LOGGEDIN;
            }

            // assumption: after a SUCCESSFUL login attempt, the incoming client WILL receive a new IoSession from the game server

            // updated session CLIENT_HWID attribute will be set when the player log in the game
            onlineRemoteHwids.add(hwid);
            hostHwidCache.addEntry(remoteHost, hwid);
            hostHwidCache.addEntry(client.getRemoteAddress(), hwid);
            associateHwidAccountIfAbsent(hwid, accountId);

            return AntiMulticlientResult.SUCCESS;
        } finally {
            sessionInit.finalize(remoteHost);
        }
    }

    private static void associateHwidAccountIfAbsent(Hwid hwid, int accountId) {
        try (Connection con = DatabaseConnection.getConnection()) {
            List<Hwid> hwids = SessionDAO.getHwidsForAccount(con, accountId);

            boolean containsRemoteHwid = hwids.stream().anyMatch(accountHwid -> accountHwid.equals(hwid));
            if (containsRemoteHwid) {
                return;
            }

            if (hwids.size() < GameConfig.getServerInt("max_allowed_account_hwid")) {
                Instant expiry = HwidAssociationExpiry.getHwidAccountExpiry(0);
                SessionDAO.registerAccountAccess(con, accountId, hwid, expiry);
            }
        } catch (SQLException ex) {
            log.warn("Failed to associate hwid {} with account id {}", hwid, accountId, ex);
        }
    }

    private static Client fetchInTransitionSessionClient(Client client) {
        Hwid hwid = SessionCoordinator.getInstance().getGameSessionHwid(client);
        if (hwid == null) {   // maybe this session was currently in-transition?
            return null;
        }

        Client fakeClient = Client.createMock();
        fakeClient.setHwid(hwid);
        Integer chrId = Server.getInstance().freeCharacteridInTransition(client);
        if (chrId != null) {
            try {
                fakeClient.setAccID(Character.loadCharFromDB(chrId, client, false).getAccountId());
            } catch (Exception sqle) {
                sqle.printStackTrace();
            }
        }

        return fakeClient;
    }

    public void closeSession(Client client, Boolean immediately) {
        if (client == null) {
            client = fetchInTransitionSessionClient(client);
            if (client == null) { // 若获取不到有效客户端，直接返回
                return;
            }
        }

        Hwid hwid = client.getHwid();
        int accountId = client.getAccID();
        String remoteHost = getSessionRemoteHost(client); // 用户标识（IP+HWID）
        client.setHwid(null); // making sure to clean up calls to this function on login phase
        if (hwid != null) {
            onlineRemoteHwids.remove(hwid);
        }

        final boolean isGameSession = hwid != null;
        if (isGameSession) {
            onlineClients.remove(client.getAccID());
        } else {
            Client loggedClient = onlineClients.get(client.getAccID());

            // do not remove an online game session here, only login session
            if (loggedClient != null && loggedClient.getSessionId() == client.getSessionId()) {
                onlineClients.remove(client.getAccID());
            }
        }
        // 3. 清理用户-账号关联记录（若之前添加了userAccountMap）
        String ip = getRealIp(remoteHost);
        Set<Integer> userAccounts = userAccountMap.get(ip);
        if (userAccounts != null) {
            boolean removed = userAccounts.remove(accountId);
            if (removed) {
                log.info("【多开清理】IP: {}, 账号ID: {} 已从多开列表移除，剩余账号数: {}", 
                         ip, accountId, userAccounts.size());
            }
            if (userAccounts.isEmpty()) {
                userAccountMap.remove(ip); // 为空时移除键，节省内存
                log.info("【多开清理】IP: {} 的账号列表已清空，移除该IP记录", ip);
            }
        } else if (accountId > 0) {
            // 仅对"真实账号却在多开列表里找不到"的情况告警；未登录会话(accId 默认 -4 / 登出后置 0)
            // 关闭时本就不在多开列表中，属正常连接(多为扫描器/机器人探测端口)，无需打 WARN 刷屏。
            log.warn("【多开清理】IP: {}, 账号ID: {} 未在多开列表中找到", ip, accountId);
        }
        if (immediately != null && immediately) {
            client.closeSession();
        }
    }

    public Hwid pickLoginSessionHwid(Client client) {
        String remoteHost = client.getRemoteAddress();
        // thanks BHB, resinate for noticing players from same network not being able to login
        return hostHwidCache.removeEntryAndGetItsHwid(remoteHost);
    }

    public Hwid getGameSessionHwid(Client client) {
        String remoteHost = getSessionRemoteHost(client);
        return hostHwidCache.getEntryHwid(remoteHost);
    }

    public void clearExpiredHwidHistory() {
        hostHwidCache.clearExpired();
    }

    public void runUpdateLoginHistory() {
        loginStorage.clearExpiredAttempts();
    }

    public void printSessionTrace() {
        if (!onlineClients.isEmpty()) {
            List<Entry<Integer, Client>> elist = new ArrayList<>(onlineClients.entrySet());
            String commaSeparatedClients = elist.stream()
                    .map(Entry::getKey)
                    .sorted(Integer::compareTo)
                    .map(Object::toString)
                    .collect(Collectors.joining(", "));

            log.debug("Current online clients: {}", commaSeparatedClients);
        }

        if (!onlineRemoteHwids.isEmpty()) {
            List<Hwid> hwids = new ArrayList<>(onlineRemoteHwids);
            hwids.sort(Comparator.comparing(Hwid::hwid));

            log.debug("Current online HWIDs: {}", hwids.stream()
                    .map(Hwid::hwid)
                    .collect(Collectors.joining(" ")));
        }

        if (!loginRemoteHosts.isEmpty()) {
            List<Entry<String, Client>> elist = new ArrayList<>(loginRemoteHosts.entrySet());
            elist.sort(Entry.comparingByKey());

            log.debug("Current login sessions: {}", loginRemoteHosts.entrySet().stream()
                    .sorted(Entry.comparingByKey())
                    .map(entry -> "(" + entry.getKey() + ", client: " + entry.getValue())
                    .collect(Collectors.joining(", ")));
        }
    }

    public void printSessionTrace(Client c) {
        String str = "Opened server sessions:\r\n\r\n";

        if (!onlineClients.isEmpty()) {
            List<Entry<Integer, Client>> elist = new ArrayList<>(onlineClients.entrySet());
            elist.sort(Entry.comparingByKey());

            str += ("Current online clients:\r\n");
            for (Entry<Integer, Client> e : elist) {
                str += ("  " + e.getKey() + "\r\n");
            }
        }

        if (!onlineRemoteHwids.isEmpty()) {
            List<Hwid> hwids = new ArrayList<>(onlineRemoteHwids);
            hwids.sort(Comparator.comparing(Hwid::hwid));

            str += ("Current online HWIDs:\r\n");
            for (Hwid s : hwids) {
                str += ("  " + s + "\r\n");
            }
        }

        if (!loginRemoteHosts.isEmpty()) {
            List<Entry<String, Client>> elist = new ArrayList<>(loginRemoteHosts.entrySet());

            elist.sort((e1, e2) -> e1.getKey().compareTo(e2.getKey()));

            str += ("Current login sessions:\r\n");
            for (Entry<String, Client> e : elist) {
                str += ("  " + e.getKey() + ", IP: " + e.getValue().getRemoteAddress() + "\r\n");
            }
        }

        c.getAbstractPlayerInteraction().npcTalk(NpcId.TEMPLE_KEEPER, str);
    }
}
