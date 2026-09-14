package org.gms.config;

import org.flywaydb.core.Flyway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;

@Configuration
public class FlywayRepairConfig {
    private static final Logger log = LoggerFactory.getLogger(FlywayRepairConfig.class);
    private static final String FAILED_VERSION = "2.1.91";

    @Bean
    public FlywayMigrationStrategy flywayMigrationStrategy() {
        return flyway -> {
            clearFailedVersion(flyway);
            flyway.repair();
            flyway.migrate();
        };
    }

    private static void clearFailedVersion(Flyway flyway) {
        String table = flyway.getConfiguration().getTable();
        String sql = "DELETE FROM `" + table + "` WHERE `version` = ? AND `success` = 0";
        try (Connection connection = flyway.getConfiguration().getDataSource().getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, FAILED_VERSION);
            int removed = statement.executeUpdate();
            if (removed > 0) {
                log.warn("Removed failed Flyway migration {} so startup can retry it", FAILED_VERSION);
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to clear Flyway history for " + FAILED_VERSION, e);
        }
    }
}
