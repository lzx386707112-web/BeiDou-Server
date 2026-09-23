package org.gms.config;

import com.alibaba.druid.pool.DruidDataSource;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class MybatisFlexFallbackConfigTest {

    @Test
    void databaseOperationsHaveBoundedTimeouts() {
        StandardEnvironment environment = new StandardEnvironment();
        environment.getPropertySources().addFirst(new MapPropertySource("test", Map.of(
                "mybatis-flex.datasource.mysql.driver-class-name", "com.mysql.cj.jdbc.Driver",
                "mybatis-flex.datasource.mysql.url", "jdbc:mysql://localhost/beidou",
                "mybatis-flex.datasource.mysql.username", "root",
                "mybatis-flex.datasource.mysql.password", "root")));

        DruidDataSource dataSource = (DruidDataSource) new MybatisFlexFallbackConfig().fallbackDataSource(environment);
        try {
            assertEquals(MybatisFlexFallbackConfig.CONNECTION_WAIT_TIMEOUT_MS, dataSource.getMaxWait());
            assertEquals(MybatisFlexFallbackConfig.CONNECT_TIMEOUT_MS, dataSource.getConnectTimeout());
            assertEquals(MybatisFlexFallbackConfig.SOCKET_TIMEOUT_MS, dataSource.getSocketTimeout());
            assertEquals(MybatisFlexFallbackConfig.QUERY_TIMEOUT_SECONDS, dataSource.getQueryTimeout());
        } finally {
            dataSource.close();
        }
    }
}
