package org.gms.config;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.configuration.Configuration;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

import static org.mockito.AdditionalMatchers.aryEq;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class FlywayRepairConfigTest {
    private static final String HISTORY_TABLE = "flyway_schema_history";

    @Test
    void migratesFreshDatabaseWhenHistoryTableDoesNotExist() throws Exception {
        FlywayTestContext context = flywayContext(false);

        strategy().migrate(context.flyway());

        verify(context.connection(), never()).prepareStatement(anyString());
        verify(context.flyway(), never()).repair();
        verify(context.flyway()).migrate();
    }

    @Test
    void clearsFailedVersionWhenHistoryTableExists() throws Exception {
        FlywayTestContext context = flywayContext(true);
        PreparedStatement statement = mock(PreparedStatement.class);
        when(context.connection().prepareStatement(
                "DELETE FROM `flyway_schema_history` WHERE `version` = ? AND `success` = 0"))
                .thenReturn(statement);
        when(statement.executeUpdate()).thenReturn(1);

        strategy().migrate(context.flyway());

        verify(statement).setString(1, "2.1.91");
        verify(statement).executeUpdate();
        verify(context.flyway()).repair();
        verify(context.flyway()).migrate();
    }

    private static FlywayMigrationStrategy strategy() {
        return new FlywayRepairConfig().flywayMigrationStrategy();
    }

    private static FlywayTestContext flywayContext(boolean historyTableExists) throws Exception {
        Flyway flyway = mock(Flyway.class);
        Configuration configuration = mock(Configuration.class);
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        DatabaseMetaData metadata = mock(DatabaseMetaData.class);
        ResultSet tables = mock(ResultSet.class);

        when(flyway.getConfiguration()).thenReturn(configuration);
        when(configuration.getTable()).thenReturn(HISTORY_TABLE);
        when(configuration.getDataSource()).thenReturn(dataSource);
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.getCatalog()).thenReturn("beidou");
        when(connection.getMetaData()).thenReturn(metadata);
        when(metadata.getTables(eq("beidou"), isNull(), eq(HISTORY_TABLE), aryEq(new String[]{"TABLE"})))
                .thenReturn(tables);
        when(tables.next()).thenReturn(historyTableExists);
        when(tables.getString("TABLE_NAME")).thenReturn(HISTORY_TABLE);

        return new FlywayTestContext(flyway, connection);
    }

    private record FlywayTestContext(Flyway flyway, Connection connection) {
    }
}
