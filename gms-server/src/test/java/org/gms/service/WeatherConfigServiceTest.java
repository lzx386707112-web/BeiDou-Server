package org.gms.service;

import org.gms.dao.entity.WeatherConfigDO;
import org.gms.dao.entity.WeatherRegionConfigDO;
import org.gms.dao.mapper.WeatherConfigMapper;
import org.gms.dao.mapper.WeatherRegionConfigMapper;
import org.gms.server.weather.WeatherConfigSnapshot;
import org.gms.server.weather.WeatherRegion;
import org.gms.server.weather.WeatherRuntime;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class WeatherConfigServiceTest {
    @AfterEach
    void reset() {
        WeatherRuntime.clearOverride();
        WeatherRuntime.replaceConfig(WeatherConfigSnapshot.defaults());
    }

    @Test
    void initializeSetsTimestampsOnDefaultRows() {
        WeatherConfigMapper configMapper = mock(WeatherConfigMapper.class);
        WeatherRegionConfigMapper regionMapper = mock(WeatherRegionConfigMapper.class);
        AtomicReference<WeatherConfigDO> global = new AtomicReference<>();
        List<WeatherRegionConfigDO> regions = new ArrayList<>();

        when(configMapper.selectOneById(1)).thenAnswer(ignored -> global.get());
        doAnswer(invocation -> {
            global.set(invocation.getArgument(0));
            return 1;
        }).when(configMapper).insert(any(WeatherConfigDO.class));
        when(regionMapper.selectAll()).thenReturn(regions);
        doAnswer(invocation -> {
            regions.add(invocation.getArgument(0));
            return 1;
        }).when(regionMapper).insert(any(WeatherRegionConfigDO.class));

        new WeatherConfigService(configMapper, regionMapper).initialize();

        assertNotNull(global.get());
        assertNotNull(global.get().getUpdateTime());
        assertEquals(WeatherRegion.values().length, regions.size());
        assertTrue(regions.stream().allMatch(row -> row.getUpdateTime() != null));
    }
}
