package org.gms.service;

import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.gms.dao.entity.WeatherConfigDO;
import org.gms.dao.entity.WeatherRegionConfigDO;
import org.gms.dao.mapper.WeatherConfigMapper;
import org.gms.dao.mapper.WeatherRegionConfigMapper;
import org.gms.exception.BizException;
import org.gms.model.dto.weather.WeatherConfigDTO;
import org.gms.model.dto.weather.WeatherConfigUpdateDTO;
import org.gms.model.dto.weather.WeatherOverrideDTO;
import org.gms.model.dto.weather.WeatherRegionDTO;
import org.gms.model.dto.weather.WeatherRegionUpdateDTO;
import org.gms.model.dto.weather.WeatherStateDTO;
import org.gms.net.server.Server;
import org.gms.server.weather.WeatherConfigSnapshot;
import org.gms.server.weather.WeatherPackets;
import org.gms.server.weather.WeatherProfile;
import org.gms.server.weather.WeatherRegion;
import org.gms.server.weather.WeatherRuntime;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class WeatherConfigService {
    private static final int PROFILE_COUNT = WeatherProfile.values().length;
    private static final long MIN_DAY_MS = 60L * 60L * 1000L;
    private static final long MAX_DAY_MS = 24L * 60L * 60L * 1000L;
    private static final long MIN_CHANGE_MS = 60_000L;
    private static final long MAX_CHANGE_MS = 24L * 60L * 60L * 1000L;
    private static final long MAX_OVERRIDE_MS = 24L * 60L * 60L * 1000L;
    private static final double MAX_WEIGHT = 1000d;

    private final WeatherConfigMapper weatherConfigMapper;
    private final WeatherRegionConfigMapper weatherRegionConfigMapper;

    @PostConstruct
    @Transactional(rollbackFor = Exception.class)
    public synchronized void initialize() {
        ensureDefaults();
        reload();
    }

    public WeatherConfigDTO config() {
        WeatherConfigSnapshot snapshot = WeatherRuntime.config();
        return new WeatherConfigDTO(snapshot.enabled(), snapshot.dayLengthMs(),
                snapshot.changeIntervalMs(), snapshot.overrideHoldMs(),
                snapshot.rainbowDurationSec());
    }

    public List<WeatherRegionDTO> regions() {
        WeatherConfigSnapshot snapshot = WeatherRuntime.config();
        return Arrays.stream(WeatherRegion.values()).map(region -> {
            WeatherConfigSnapshot.RegionConfig value = snapshot.region(region);
            List<Double> weights = Arrays.stream(value.weights()).boxed().toList();
            return new WeatherRegionDTO(region.name(),
                    WeatherRuntime.skyForRegion(region).profileName(),
                    value.forcedProfile() == null ? null : value.forcedProfile().profileName(),
                    weights, value.nightTint(), value.paletteId());
        }).toList();
    }

    public WeatherStateDTO state() {
        int online = 0;
        for (var world : Server.getInstance().getWorlds()) {
            if (world.getPlayerStorage() != null) {
                online += world.getPlayerStorage().getAllCharacters().size();
            }
        }
        WeatherProfile override = WeatherRuntime.overrideProfile();
        return new WeatherStateDTO(WeatherRuntime.config().enabled(), WeatherRuntime.minuteOfDay(),
                WeatherRuntime.nightLevel(), WeatherRuntime.isWeatherOverridden(),
                override == null ? null : override.profileName(), WeatherRuntime.isTimeFrozen(),
                WeatherRuntime.overrideRemainingSec(), WeatherRuntime.nextRollInSec(), online);
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int updateConfig(WeatherConfigUpdateDTO request) {
        validateConfig(request);
        WeatherConfigDO value = weatherConfigMapper.selectOneById(1);
        value.setEnabled(request.getEnabled());
        value.setDayLengthMs(request.getDayLengthMs());
        value.setChangeIntervalMs(request.getChangeIntervalMs());
        value.setOverrideHoldMs(request.getOverrideHoldMs());
        value.setRainbowDurationSec(request.getRainbowDurationSec());
        value.setUpdateTime(new Date());
        weatherConfigMapper.update(value);
        reload();
        return WeatherPackets.broadcastAll(true);
    }

    @Transactional(rollbackFor = Exception.class)
    public synchronized int updateRegion(String regionName, WeatherRegionUpdateDTO request) {
        WeatherRegion region = parseRegion(regionName);
        validateRegion(request);
        WeatherRegionConfigDO value = weatherRegionConfigMapper.selectOneById(region.name());
        value.setForcedProfile(normalizeProfile(request.getForcedProfile()));
        setWeights(value, request.getWeights());
        value.setNightTint(request.getNightTint());
        value.setPaletteId(request.getPaletteId());
        value.setUpdateTime(new Date());
        weatherRegionConfigMapper.update(value);
        reload();
        return WeatherPackets.broadcastAll(true);
    }

    public synchronized int override(WeatherOverrideDTO request) {
        if (request == null) throw BizException.illegalArgument("天气覆盖配置不能为空");
        WeatherProfile profile = null;
        if (request.getProfile() != null && !request.getProfile().isBlank()) {
            profile = WeatherProfile.parse(request.getProfile());
            if (profile == null) throw BizException.illegalArgument("未知天气类型");
        }
        Integer minute = request.getMinuteOfDay();
        if (minute != null && (minute < 0 || minute >= 1440)) {
            throw BizException.illegalArgument("时间必须在 0 到 1439 分钟之间");
        }
        int durationMinutes = request.getDurationMinutes() == null
                ? (int) (WeatherRuntime.config().overrideHoldMs() / 60_000L)
                : request.getDurationMinutes();
        if (durationMinutes < 1 || durationMinutes > 1440) {
            throw BizException.illegalArgument("覆盖时长必须在 1 到 1440 分钟之间");
        }
        try {
            WeatherRuntime.override(profile, minute, durationMinutes * 60_000L);
        } catch (IllegalArgumentException exception) {
            throw BizException.illegalArgument(exception.getMessage());
        }
        return WeatherPackets.broadcastAll(true);
    }

    public synchronized int clearOverride() {
        WeatherRuntime.clearOverride();
        WeatherRuntime.rollIfDue();
        return WeatherPackets.broadcastAll(true);
    }

    public int broadcast() {
        return WeatherPackets.broadcastAll(true);
    }

    private void reload() {
        WeatherConfigDO global = weatherConfigMapper.selectOneById(1);
        Map<WeatherRegion, WeatherConfigSnapshot.RegionConfig> regions = new EnumMap<>(WeatherRegion.class);
        for (WeatherRegionConfigDO row : weatherRegionConfigMapper.selectAll()) {
            WeatherRegion region;
            try { region = WeatherRegion.valueOf(row.getRegion()); }
            catch (IllegalArgumentException ignored) { continue; }
            regions.put(region, new WeatherConfigSnapshot.RegionConfig(
                    WeatherProfile.parse(row.getForcedProfile()), weights(row),
                    row.getNightTint(), row.getPaletteId()));
        }
        WeatherRuntime.replaceConfig(new WeatherConfigSnapshot(global.getEnabled(),
                global.getDayLengthMs(), global.getChangeIntervalMs(), global.getOverrideHoldMs(),
                global.getRainbowDurationSec(), regions));
        WeatherRuntime.rollIfDue();
    }

    private void ensureDefaults() {
        if (weatherConfigMapper.selectOneById(1) == null) {
            weatherConfigMapper.insert(WeatherConfigDO.builder().id(1).enabled(true)
                    .dayLengthMs(14_400_000L).changeIntervalMs(900_000L)
                    .overrideHoldMs(3_600_000L).rainbowDurationSec(180)
                    .updateTime(new Date()).build());
        }
        Map<String, WeatherRegionConfigDO> existing = new HashMap<>();
        weatherRegionConfigMapper.selectAll().forEach(row -> existing.put(row.getRegion(), row));
        for (WeatherRegion region : WeatherRegion.values()) {
            if (existing.containsKey(region.name())) continue;
            WeatherRegionConfigDO row = WeatherRegionConfigDO.builder().region(region.name())
                    .forcedProfile(region.forcedProfile() == null ? null : region.forcedProfile().profileName())
                    .nightTint(region.tint()).paletteId(region.paletteId())
                    .updateTime(new Date()).build();
            setWeights(row, Arrays.stream(region.weights()).boxed().toList());
            weatherRegionConfigMapper.insert(row);
        }
    }

    private void validateConfig(WeatherConfigUpdateDTO value) {
        if (value == null || value.getEnabled() == null || value.getDayLengthMs() == null
                || value.getChangeIntervalMs() == null || value.getOverrideHoldMs() == null
                || value.getRainbowDurationSec() == null) {
            throw BizException.illegalArgument("全局天气配置字段不完整");
        }
        if (value.getDayLengthMs() < MIN_DAY_MS || value.getDayLengthMs() > MAX_DAY_MS)
            throw BizException.illegalArgument("游戏日长度必须在 1 到 24 小时之间");
        if (value.getChangeIntervalMs() < MIN_CHANGE_MS || value.getChangeIntervalMs() > MAX_CHANGE_MS)
            throw BizException.illegalArgument("天气切换周期必须在 1 分钟到 24 小时之间");
        if (value.getOverrideHoldMs() < MIN_CHANGE_MS || value.getOverrideHoldMs() > MAX_OVERRIDE_MS)
            throw BizException.illegalArgument("默认覆盖时长必须在 1 分钟到 24 小时之间");
        if (value.getRainbowDurationSec() < 0 || value.getRainbowDurationSec() > 3600)
            throw BizException.illegalArgument("彩虹时长必须在 0 到 3600 秒之间");
    }

    private void validateRegion(WeatherRegionUpdateDTO value) {
        if (value == null || value.getWeights() == null || value.getWeights().size() != PROFILE_COUNT
                || value.getNightTint() == null || value.getPaletteId() == null) {
            throw BizException.illegalArgument("区域天气配置字段不完整");
        }
        if (value.getForcedProfile() != null && !value.getForcedProfile().isBlank()
                && WeatherProfile.parse(value.getForcedProfile()) == null) {
            throw BizException.illegalArgument("未知的区域强制天气");
        }
        double total = 0d;
        for (Double weight : value.getWeights()) {
            if (weight == null || !Double.isFinite(weight) || weight < 0d || weight > MAX_WEIGHT)
                throw BizException.illegalArgument("天气权重必须在 0 到 1000 之间");
            total += weight;
        }
        if (total <= 0d) throw BizException.illegalArgument("区域天气权重总和必须大于 0");
        if (value.getNightTint() < 0 || value.getNightTint() > 0xFFFFFF)
            throw BizException.illegalArgument("夜色色值必须是 0x000000 到 0xFFFFFF");
        if (value.getPaletteId() < 0 || value.getPaletteId() >= WeatherRegion.values().length)
            throw BizException.illegalArgument("调色板编号超出客户端支持范围");
    }

    private WeatherRegion parseRegion(String value) {
        try { return WeatherRegion.valueOf(value.toUpperCase(java.util.Locale.ROOT)); }
        catch (RuntimeException ignored) { throw BizException.illegalArgument("未知天气区域: " + value); }
    }

    private String normalizeProfile(String value) {
        WeatherProfile profile = WeatherProfile.parse(value);
        return profile == null ? null : profile.profileName();
    }

    private double[] weights(WeatherRegionConfigDO row) {
        return new double[]{row.getClearWeight().doubleValue(), row.getRainWeight().doubleValue(),
                row.getSnowWeight().doubleValue(), row.getOvercastWeight().doubleValue(),
                row.getStormWeight().doubleValue(), row.getBlizzardWeight().doubleValue(),
                row.getLeavesWeight().doubleValue(), row.getBlossomWeight().doubleValue(),
                row.getSandstormWeight().doubleValue()};
    }

    private void setWeights(WeatherRegionConfigDO row, List<Double> values) {
        List<BigDecimal> weights = new ArrayList<>(PROFILE_COUNT);
        values.forEach(value -> weights.add(BigDecimal.valueOf(value)));
        row.setClearWeight(weights.get(0)); row.setRainWeight(weights.get(1));
        row.setSnowWeight(weights.get(2)); row.setOvercastWeight(weights.get(3));
        row.setStormWeight(weights.get(4)); row.setBlizzardWeight(weights.get(5));
        row.setLeavesWeight(weights.get(6)); row.setBlossomWeight(weights.get(7));
        row.setSandstormWeight(weights.get(8));
    }
}
