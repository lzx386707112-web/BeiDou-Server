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
package org.gms.net.server.handlers.login;

import org.gms.client.Client;
import org.gms.client.DefaultDates;
import org.gms.config.GameConfig;
import org.gms.net.PacketHandler;
import org.gms.net.packet.InPacket;
import org.gms.net.server.Server;
import org.gms.net.server.coordinator.session.Hwid;
import org.gms.net.server.coordinator.session.SessionCoordinator;
import org.gms.util.BCrypt;
import org.gms.util.DatabaseConnection;
import org.gms.util.HexTool;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.security.NoSuchAlgorithmException;
import java.sql.*;
import java.util.Calendar;

public final class LoginPasswordHandler implements PacketHandler {

    // 配置同一个IP或MAC允许的最大账号数量
    private int MAX_ACCOUNTS_PER_IP_OR_MAC = 0;
    private static final Logger log = LoggerFactory.getLogger(LoginPasswordHandler.class);

    @Override
    public boolean validateState(Client c) {
        return !c.isLoggedIn();
    }

    @Override
    public final void handlePacket(InPacket p, Client c) {
        String remoteHost = c.getRemoteAddress();
        if (remoteHost.contentEquals("null")) {
            c.sendPacket(PacketCreator.getLoginFailed(14));          // thanks Alchemist for noting remoteHost could be null
            return;
        }

        String login = p.readString();
        String pwd = p.readString();
        c.setAccountName(login);

        p.skip(6);   // localhost masked the initial part with zeroes...
        byte[] hwidNibbles = p.readBytes(4);
        Hwid hwid = new Hwid(HexTool.toCompactHexString(hwidNibbles));
        int loginok = c.login(login, pwd, hwid);
        if (loginok == 6) {
            c.sendPacket(PacketCreator.getLoginFailed(6));
            return;
        }

        if (GameConfig.getServerBoolean("automatic_register") && loginok == 5) {
            try {
                String clientIp = remoteHost;
                String clientMac = c.getMacs().isEmpty() ? "" : c.getMacs().iterator().next();

                if (!isAllowedRegistration(clientIp, clientMac)) {
                    log.info("该IP或者Mac注册账号已达上限");
                    c.sendPacket(PacketCreator.getLoginFailed(10));
                    return;
                }
                // 执行账号注册
                try (Connection con = DatabaseConnection.getConnection();
//                    PreparedStatement ps = con.prepareStatement("INSERT INTO accounts (name, password, birthday, tempban) VALUES (?, ?, ?, ?);", Statement.RETURN_GENERATED_KEYS)) { //Jayd: Added birthday, tempban
                     PreparedStatement ps = con.prepareStatement(
                             "INSERT INTO accounts (name, password, birthday, tempban, ip, macs) " + "VALUES (?, ?, ?, ?, ?, ?);",
                             Statement.RETURN_GENERATED_KEYS)) {
                    ps.setString(1, login);
                    ps.setString(2, GameConfig.getServerBoolean("bcrypt_migration") ? BCrypt.hashpw(pwd, BCrypt.gensalt(12)) : BCrypt.hashpwSHA512(pwd));
                    ps.setDate(3, Date.valueOf(DefaultDates.getBirthday()));
                    ps.setTimestamp(4, Timestamp.valueOf(DefaultDates.getTempban()));
                    ps.setString(5, clientIp);  // 存入注册IP
                    ps.setString(6, clientMac); // 存入注册MAC
                    ps.executeUpdate();
                    try (ResultSet rs = ps.getGeneratedKeys()) {
                        rs.next();
                        c.setAccID(rs.getInt(1));
                    }
                }
            } catch (SQLException | NoSuchAlgorithmException e) {
                c.setAccID(-1);
                log.error("自动注册失败，账号: {}", login, e);
                c.sendPacket(PacketCreator.getLoginFailed(6));
                return;
            }
            loginok = c.login(login, pwd, hwid);
            if (loginok == 6) {
                c.sendPacket(PacketCreator.getLoginFailed(6));
                return;
            }
        }

        if (GameConfig.getServerBoolean("bcrypt_migration") && (loginok <= -10)) { // -10 means migration to bcrypt, -23 means TOS wasn't accepted
            try (Connection con = DatabaseConnection.getConnection();
                 PreparedStatement ps = con.prepareStatement("UPDATE accounts SET password = ? WHERE name = ?;")) {
                ps.setString(1, BCrypt.hashpw(pwd, BCrypt.gensalt(12)));
                ps.setString(2, login);
                ps.executeUpdate();
            } catch (SQLException e) {
                log.error("登录密码迁移失败，账号: {}", login, e);
                c.sendPacket(PacketCreator.getLoginFailed(6));
                return;
            }
            loginok = (loginok == -10) ? 0 : 23;
        }

        if (c.hasBannedIP() || c.hasBannedMac()) {
            c.sendPacket(PacketCreator.getLoginFailed(3));
            return;
        }
        Calendar tempban = c.getTempBanCalendarFromDB();
        if (tempban != null) {
            if (tempban.getTimeInMillis() > Calendar.getInstance().getTimeInMillis()) {
                c.sendPacket(PacketCreator.getTempBan(tempban.getTimeInMillis(), c.getGReason()));
                return;
            }
        }
        if (loginok == 3) {
            c.sendPacket(PacketCreator.getPermBan(c.getGReason()));//crashes but idc :D
            return;
        } else if (loginok == 7) {
            handleAccountKick(c);
        } else if (loginok != 0) {
            c.sendPacket(PacketCreator.getLoginFailed(loginok));
            return;
        }
        if (c.finishLogin() == 0) {
            c.checkChar(c.getAccID());
            login(c);
        } else {
            c.sendPacket(PacketCreator.getLoginFailed(7));
        }
    }

    /**
     * 如果loginok=7，需要顶号，重置在线状态
     */
    private void handleAccountKick(Client c) {
        int accountId = c.getAccID();
        if (accountId <= 0) {
            return;
        }
        Server.getInstance().resetLoggedInByAccountId(accountId);
        log.info("用户顶号 accountId=" + accountId);
    }

    /**
     * 检查IP和MAC的注册数量是否超过限制
     */
    private boolean isAllowedRegistration(String ip, String mac) throws SQLException {
        MAX_ACCOUNTS_PER_IP_OR_MAC = GameConfig.getServerInt("max_accounts_per_ip_or_mac");
        if (MAX_ACCOUNTS_PER_IP_OR_MAC <= 0) {
            return true;
        }
        try (Connection con = DatabaseConnection.getConnection()) {
            // 检查IP注册数量
            try (PreparedStatement ps = con.prepareStatement(
                    "SELECT COUNT(*) FROM accounts WHERE ip = ?")) {
                ps.setString(1, ip);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next() && rs.getInt(1) >= MAX_ACCOUNTS_PER_IP_OR_MAC) {
                        return false;
                    }
                }
            }

            // 检查MAC注册数量
            if (mac != null && !mac.isEmpty()) {
                try (PreparedStatement ps = con.prepareStatement(
                        "SELECT COUNT(*) FROM accounts WHERE macs = ?")) {
                    ps.setString(1, mac);
                    try (ResultSet rs = ps.executeQuery()) {
                        if (rs.next() && rs.getInt(1) >= MAX_ACCOUNTS_PER_IP_OR_MAC) {
                            return false;
                        }
                    }
                }
            }

            return true;
        }
    }

    private static void login(Client c) {
        c.sendPacket(PacketCreator.getAuthSuccess(c));//why the fk did I do c.getAccountName()?
        SessionCoordinator.getInstance().cacheMultiOpenId(c, c.getAccID());  //loginok == 4，但是会导致限制多开参数 deterred_multi_client == true 时密码错误一次返回REMOTE_REACHED_LIMIT，需要重开客户端
        Server.getInstance().registerLoginState(c);
    }
}
