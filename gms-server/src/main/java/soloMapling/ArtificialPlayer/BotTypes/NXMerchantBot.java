package soloMapling.ArtificialPlayer.BotTypes;

import org.gms.client.Character;
import org.gms.server.Trade;
import soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotTradeSystem.BotTradeSM;
import soloMapling.FreeMarket.MarketBotAmbient;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.MarketBotDirector;

import java.util.Collections;
import java.util.List;

import static soloMapling.ArtificialPlayer.BotCommandsPack.MapleMessengerCommands.botLeaveMessenger;
import static soloMapling.ArtificialPlayer.BotCommandsPack.MapleMessengerCommands.botSendChatFull;
import static soloMapling.ArtificialPlayer.BotCommandsPack.MapleMessengerCommands.isMessengerInviteAccepted;
import static soloMapling.ArtificialPlayer.BotCommandsPack.MapleMessengerCommands.sendMessengerInviteComplete;
import static soloMapling.ArtificialPlayer.BotHelpers.sleepAmountSeconds;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.nudgeAwayFromOverlap;
import static soloMapling.ArtificialPlayer.BotTypeManager.BotType.BUYING_MERCHANT_BOT;
import static soloMapling.ArtificialPlayer.BotTypeManager.BotType.SELLING_MERCHANT_BOT;
import static soloMapling.ArtificialPlayer.BotTypeManager.convertBotType;
import static soloMapling.BotLogger.log;
import static soloMapling.Environment.EnvironmentManager.botMoveToPlatformAnyUnoccupiedSpot;
import static soloMapling.Environment.EnvironmentManager.getCurrentPlatform;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateItem;
import static soloMapling.server.NXCodeManager.createCompleteNXCode;
import static soloMapling.server.NXCodeManager.generateGiftCardCode;
import static soloMapling.server.SoloMaplingUtilities.getRandomElement;
import static soloMapling.server.SoloMaplingUtilities.random;
import static soloMapling.server.SoloMaplingUtilities.rollChanceInverse;
import static soloMapling.server.SoloMaplingUtilities.waitForCondition;

public class NXMerchantBot extends BotSM {
    private NXState nxState = NXState.SETUP;
    private List<String> hint = Collections.singletonList(getChr().getName());
    private int advertiseCycles = 0;
    private static final int MAX_ADVERTISE_CYCLES = 15;

    private enum NXState {
        SETUP,
        ADVERTISE,
        CHECK_TRADES,
        DELIVER_CODE,
        CONVERT_BACK
    }

    private static final List<String> FLAVOR_NODES = List.of("ScamMessages", "BeggingMessages", "RWTMessages", "FunnyMessages");

    public NXMerchantBot(Character character) {
        super(character);
        dialoguePath = "MerchantBotDialogue.yaml";
        botType = "MerchantBot";
    }

    @Override
    public boolean usesSharedMarketTick() {
        return true;
    }

    private void setupNXSale() {
        // Use a filler item as the visual representation in trade
        org.gms.client.inventory.Item filler = generateItem(4031865, 1, 100);
        getTradeInventory().setItemForSaleMain(filler);
        getTradeWants().resetTradeWants();
        int fiftyMill = 50_000_000;
        getTradeWants().setMesoWanted(fiftyMill);
        setTradeMode(BotTradeSM.TradeMode.SELLING);
        resetLastTradeResult();
        resetLastTradedCharacter();
    }

    private void advertise() {
        List<String> messages = List.of(
                "出1万点券兑换码，五千万金币，交易我！",
                "出点券码一万点，五千万，别刀太狠。",
                "点券码一万点换五千万，只接受交易。",
                "正经出点券码，一万点五千万，要的密。",
                "出点券一万点，五千万，先到先得。",
                "卖点券码，一万点五千万，认真的来。",
                "有点券码，一万点换五千万，交易窗见。"
        );
        if (MarketBotDirector.get().trySpeak(getChr())) {
            SocialCommands.BotSpeak(getChr(), getRandomElement(messages));
        }
    }

    private void deliverNXCode() {
        if (getLastTradeResult() != Trade.TradeResult.SUCCESSFUL) {
            convertBack();
            return;
        }

        SocialCommands.BotSpeak(getChr(), "我密你了。");
        sendMessengerInviteComplete(getChr(), getLastTradedCharacter());

        boolean accepted = waitForCondition(
                () -> isMessengerInviteAccepted(getChr(), getLastTradedCharacter())
        );

        if (accepted) {
            String nxCode = generateGiftCardCode();
            createCompleteNXCode(nxCode);

            botSendChatFull(getChr(), "一万点的兑换码给你，记下来，不要带横杠。", 3000);
            botSendChatFull(getChr(), nxCode, 7000);
            botSendChatFull(getChr(), "用得开心！", 2000);

            sleepAmountSeconds(2000);
            botLeaveMessenger(getChr());
        } else {
            SocialCommands.BotSpeak(getChr(), "你没接聊天邀请，那就算了。");
        }

        resetLastTradeResult();
        resetLastTradedCharacter();
    }

    private boolean tryPlatformShuffle() {
        if (!SoloMaplingConfig.marketWanderEnabled()) {
            return false;
        }
        if (rollChanceInverse(15)) {
            botMoveToPlatformAnyUnoccupiedSpot(getChr(), getCurrentPlatform(getChr()));
            if (rollChanceInverse(2)) nudgeAwayFromOverlap(getChr());
            return true;
        } else if (rollChanceInverse(40)) {
            botMoveToPlatformAnyUnoccupiedSpot(getChr(), getRandomElement(List.of("m1", "m5")));
            if (rollChanceInverse(2)) nudgeAwayFromOverlap(getChr());
            return true;
        }
        return false;
    }

    private void convertBack() {
        if (random.nextBoolean()) {
            convertBotType(getChr(), SELLING_MERCHANT_BOT);
        } else {
            convertBotType(getChr(), BUYING_MERCHANT_BOT);
        }
    }

    @Override
    public void updateState() {
        super.updateState();
        if (checkIfNotRunningOrPaused()) {
            return;
        }
        if (getState() == BotState.TRADING) {
            return;
        }
        MarketBotAmbient.act(this);
        if (MarketBotAmbient.isSitting(getChr()) || isBusy()) {
            if (MarketBotAmbient.isSitting(getChr())) {
                advertise();
            }
            return;
        }
        if (getLastTradeResult() == Trade.TradeResult.SUCCESSFUL && nxState != NXState.DELIVER_CODE && nxState != NXState.CONVERT_BACK) {
            nxState = NXState.DELIVER_CODE;
        }

        getDebugger().debugLoggingFull(
                String.format("%s NXMerchantBot: %s", getChr().getName(), nxState),
                String.format("%s", nxState));

        switch (nxState) {
            case SETUP:
                setupNXSale();
                nxState = NXState.ADVERTISE;
                break;
            case ADVERTISE:
                // 4% (1/25) Chance to advertise flavor, 96% chance to advertise NX
                if (rollChanceInverse(25)) {
                    getDialogueHandler().executeBotFlavorDialogue(getRandomElement(FLAVOR_NODES), this);
                } else {
                    advertise();
                }
                nxState = NXState.CHECK_TRADES;
                break;
            case CHECK_TRADES:
                checkForTrades();
                advertiseCycles++;
                if (getLastTradeResult() == Trade.TradeResult.SUCCESSFUL) {
                    nxState = NXState.DELIVER_CODE;
                } else if (advertiseCycles >= MAX_ADVERTISE_CYCLES) {
                    nxState = NXState.CONVERT_BACK;
                } else {
                    nxState = NXState.ADVERTISE;
                }
                break;
            case DELIVER_CODE:
                deliverNXCode();
                nxState = NXState.CONVERT_BACK;
                break;
            case CONVERT_BACK:
                convertBack();
                break;
            default:
                log("Unexpected state: " + nxState);
                state = BotState.FINISHED;
                throw new IllegalStateException("Unexpected state: " + nxState);
        }
    }

    @Override
    public void displayCommands(Character chr) {
        SocialCommands.displayPlayerChatCommands(chr, hint);
    }

    @Override
    public void processMessages() {
    }
}
