package soloMapling.FreeMarket;

import org.gms.client.Character;
import org.gms.server.Trade;
import soloMapling.ArtificialPlayer.BotHelpers;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.ArtificialPlayer.BotTradeSystem.BotTradeCommands;
import soloMapling.ArtificialPlayer.BotTradeSystem.BotTradeSM;

import java.util.concurrent.ConcurrentHashMap;

public final class MarketBotTradeHook {
    private static final ConcurrentHashMap<Integer, Long> lastTradeReplyAt = new ConcurrentHashMap<>();

    private MarketBotTradeHook() {
    }

    public static void onPlayerInvitedBot(Character player, Character botChr) {
        if (player == null || botChr == null || BotHelpers.isBot(player) || !BotHelpers.isBot(botChr)) {
            return;
        }
        BotSM bot = CharacterStorage.getBotById(botChr.getId());
        if (bot != null) {
            bot.clearBusy();
            bot.getTradeHandler().setTradePartner(player);
            if (bot.getTradeMode() == null || bot.getTradeMode() == BotTradeSM.TradeMode.NULL) {
                bot.setTradeMode(BotTradeSM.TradeMode.SELLING);
            }
        }
        Trade.visitTrade(botChr, player);
        BotTradeCommands.writeTradeChat(botChr, MarketBotFlavor.tradeOpen());
    }

    public static void onTradeChat(Character speaker, Character listener) {
        if (speaker == null || listener == null || BotHelpers.isBot(speaker) || !BotHelpers.isBot(listener)) {
            return;
        }
        if (listener.getTrade() == null) {
            return;
        }
        long now = System.currentTimeMillis();
        Long last = lastTradeReplyAt.get(listener.getId());
        if (last != null && now - last < 1200L) {
            return;
        }
        lastTradeReplyAt.put(listener.getId(), now);
        BotTradeCommands.writeTradeChat(listener, MarketBotFlavor.tradeReply());
    }
}
