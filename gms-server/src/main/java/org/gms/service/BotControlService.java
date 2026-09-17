package org.gms.service;

import com.mybatisflex.core.query.QueryWrapper;
import lombok.RequiredArgsConstructor;
import org.gms.config.GameConfig;
import org.gms.dao.entity.GameConfigDO;
import org.gms.dao.mapper.GameConfigMapper;
import org.gms.exception.BizException;
import org.gms.model.dto.botcontrol.BotControlConfigDTO;
import org.gms.model.dto.botcontrol.BotControlFieldDTO;
import org.gms.model.dto.botcontrol.BotControlStateDTO;
import org.gms.model.dto.botcontrol.BotControlUpdateDTO;
import org.gms.net.server.Server;
import org.gms.util.I18nUtil;
import org.springframework.stereotype.Service;
import soloMapling.SoloMaplingConfig;
import org.springframework.transaction.annotation.Transactional;
import soloMapling.Environment.EnvironmentManager;
import soloMapling.server.MarketBotDirector;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.gms.dao.entity.table.GameConfigDOTableDef.GAME_CONFIG_D_O;

@Service
@RequiredArgsConstructor
public class BotControlService {
    static final List<String> MARKET_CODES = List.of(
            "solo_mapling_market_auto_start",
            "solo_mapling_feature_fm_bots_enabled",
            "solo_mapling_feature_fm_merchants_enabled",
            "solo_mapling_feature_fm_region_fill_enabled",
            "solo_mapling_market_bot_max",
            "solo_mapling_market_shop_max",
            "solo_mapling_market_wander_enabled",
            "solo_mapling_market_hawk_enabled",
            "solo_mapling_market_browse_shops_enabled",
            "solo_mapling_market_idle_when_empty",
            "solo_mapling_market_tick_ms",
            "solo_mapling_market_speech_gap_ms",
            "solo_mapling_market_pathfind_per_tick"
    );

    static final List<String> APPEARANCE_CODES = List.of(
            "solo_mapling_bot_random_chinese_name",
            "solo_mapling_bot_random_skill_enabled",
            "solo_mapling_bot_random_chair_enabled",
            "solo_mapling_bot_random_body_enabled",
            "solo_mapling_bot_normal_equips_enabled",
            "solo_mapling_bot_full_equips_enabled",
            "solo_mapling_bot_nx_equips_enabled",
            "solo_mapling_bot_deferred_decoration_enabled"
    );

    private final GameConfigMapper gameConfigMapper;

    public BotControlStateDTO state() {
        int online = 0;
        for (var world : Server.getInstance().getWorlds()) {
            if (world.getPlayerStorage() != null) {
                online += world.getPlayerStorage().getAllCharacters().size();
            }
        }
        return new BotControlStateDTO(
                soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage.getAllBots().size(),
                MarketBotDirector.get().activeCount(),
                EnvironmentManager.getMarketEntranceBotCount(),
                online,
                EnvironmentManager.isMarketStartupComplete(),
                EnvironmentManager.isMarketStartupRunning());
    }

    public BotControlConfigDTO config() {
        Map<String, GameConfigDO> byCode = loadSoloMaplingRows();
        List<BotControlFieldDTO> market = fieldsInOrder(MARKET_CODES, byCode);
        List<BotControlFieldDTO> appearance = fieldsInOrder(APPEARANCE_CODES, byCode);
        Set<String> used = new HashSet<>();
        used.addAll(MARKET_CODES);
        used.addAll(APPEARANCE_CODES);
        List<String> leftover = new ArrayList<>();
        for (String code : byCode.keySet()) {
            if (!used.contains(code)) {
                leftover.add(code);
            }
        }
        leftover.sort(String::compareTo);
        return new BotControlConfigDTO(market, appearance, fieldsInOrder(leftover, byCode), List.of());
    }

    public String startMarket() {
        if (EnvironmentManager.isMarketStartupComplete()) {
            return "already";
        }
        if (EnvironmentManager.isMarketStartupRunning()) {
            return "running";
        }
        EnvironmentManager.requestMarketStartup();
        return "started";
    }

    @Transactional(rollbackFor = Exception.class)
    public int update(BotControlUpdateDTO request) {
        if (request == null || request.fields() == null || request.fields().isEmpty()) {
            throw new BizException(I18nUtil.getExceptionMessage("PARAMETER_SHOULD_NOT_EMPTY", "fields"));
        }
        Set<String> allowed = new LinkedHashSet<>(loadSoloMaplingRows().keySet());
        allowed.addAll(MARKET_CODES);
        allowed.addAll(APPEARANCE_CODES);
        int updated = 0;
        for (BotControlFieldDTO field : request.fields()) {
            if (field == null || !allowed.contains(field.code()) || !field.code().startsWith("solo_mapling_")) {
                continue;
            }
            GameConfigDO current = gameConfigMapper.selectOneById(field.id());
            if (current == null || !field.code().equals(current.getConfigCode())) {
                continue;
            }
            current.setConfigValue(field.value());
            current.setUpdateTime(new Date());
            gameConfigMapper.update(GameConfigDO.builder()
                    .id(field.id())
                    .configValue(field.value())
                    .updateTime(current.getUpdateTime())
                    .build());
            GameConfig.update(current);
            updated++;
        }
        MarketBotDirector.get().refreshTickInterval();
        if (SoloMaplingConfig.marketAutoStartEnabled()) {
            soloMapling.ArtificialPlayer.BotAutoSpawner.requestStartupIfEnabled();
        }
        return updated;
    }

    private Map<String, GameConfigDO> loadSoloMaplingRows() {
        List<GameConfigDO> rows = gameConfigMapper.selectListByQuery(
                QueryWrapper.create().where(GAME_CONFIG_D_O.CONFIG_CODE.like("solo_mapling%")));
        Map<String, GameConfigDO> byCode = new LinkedHashMap<>();
        for (GameConfigDO row : rows) {
            byCode.put(row.getConfigCode(), row);
        }
        return byCode;
    }

    private List<BotControlFieldDTO> fieldsInOrder(List<String> codes, Map<String, GameConfigDO> byCode) {
        List<BotControlFieldDTO> fields = new ArrayList<>();
        for (String code : codes) {
            GameConfigDO row = byCode.get(code);
            if (row == null) {
                continue;
            }
            fields.add(new BotControlFieldDTO(row.getId(), row.getConfigCode(), row.getConfigClazz(),
                    row.getConfigValue(), row.getConfigCode()));
        }
        return fields;
    }
}
