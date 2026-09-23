package org.gms.client;

import org.gms.manager.ServerManager;
import org.gms.net.server.coordinator.session.Hwid;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;

import javax.sql.DataSource;
import java.sql.SQLException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ClientLoginFailureTest {

    @Test
    void databaseFailureReturnsSystemError() throws Exception {
        ApplicationContext context = mock(ApplicationContext.class);
        DataSource dataSource = mock(DataSource.class);
        when(context.getBean(DataSource.class)).thenReturn(dataSource);
        when(dataSource.getConnection()).thenThrow(new SQLException("database unavailable"));
        new ServerManager().setApplicationContext(context);

        Client client = Client.createMock();

        assertEquals(6, client.login("test", "password", new Hwid("00000000")));
    }
}
