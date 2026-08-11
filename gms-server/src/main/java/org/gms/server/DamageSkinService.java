package org.gms.server;

import org.gms.client.Character;
import org.gms.util.DatabaseConnection;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

public final class DamageSkinService {
    private static final Logger log = LoggerFactory.getLogger(DamageSkinService.class);

    private DamageSkinService() {
    }

    public static int[] getSkinIds() {
        return DamageSkinCatalog.ids();
    }

    public static String getSkinName(int skinId) {
        return DamageSkinCatalog.nameOf(skinId);
    }

    public static int getSkinId(int characterId) {
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(
                     "SELECT damageSkinId FROM characters WHERE id = ?")) {
            statement.setInt(1, characterId);
            try (ResultSet result = statement.executeQuery()) {
                if (result.next()) {
                    int skinId = result.getInt("damageSkinId");
                    return DamageSkinCatalog.contains(skinId) ? skinId : 0;
                }
            }
        } catch (SQLException error) {
            log.error("Unable to load damage skin for character {}", characterId, error);
        }
        return 0;
    }

    public static boolean setSkin(Character player, int skinId) {
        if (player == null || !DamageSkinCatalog.contains(skinId)) {
            return false;
        }
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(
                     "UPDATE characters SET damageSkinId = ? WHERE id = ?")) {
            statement.setInt(1, skinId);
            statement.setInt(2, player.getId());
            if (statement.executeUpdate() != 1) {
                return false;
            }
            player.sendPacket(PacketCreator.damageSkinUpdate(skinId));
            return true;
        } catch (SQLException error) {
            log.error("Unable to save damage skin {} for character {}", skinId, player.getId(), error);
            return false;
        }
    }

    public static void sync(Character player) {
        if (player != null) {
            player.sendPacket(PacketCreator.damageSkinUpdate(getSkinId(player.getId())));
        }
    }
}
