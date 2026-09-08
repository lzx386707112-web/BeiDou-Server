package org.gms.server.life;

import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.awt.Point;
import java.util.Locale;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SpawnPointFrenzyTest {
    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class);
        ServiceProperty serviceProperty = new ServiceProperty();
        serviceProperty.setLanguage("zh-CN");
        MessageSource messageSource = mock(MessageSource.class);
        when(messageSource.getMessage(anyString(), any(Object[].class), any(Locale.class)))
                .thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(serviceProperty);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messageSource);
        new ServerManager().setApplicationContext(context);
    }

    @Test
    void duplicatePreservesSpawnContractAndUsesAcceleratedDelay() {
        Monster monster = mock(Monster.class);
        when(monster.getId()).thenReturn(100100);
        when(monster.getFh()).thenReturn(12);
        when(monster.getF()).thenReturn(1);

        SpawnPoint original = new SpawnPoint(
                monster, new Point(25, 40), false, 20, 5000, 0
        );
        original.setRespawnTimeMultiplier(0.5);
        SpawnPoint duplicate = original.duplicate();

        assertNotSame(original, duplicate);
        assertEquals(original.getMonsterId(), duplicate.getMonsterId());
        assertEquals(original.getPosition(), duplicate.getPosition());
        assertEquals(original.getMobTime(), duplicate.getMobTime());
        assertEquals(original.getTeam(), duplicate.getTeam());
        assertEquals(10_000L, duplicate.scaleRespawnDelay(20_000L));
    }
}
