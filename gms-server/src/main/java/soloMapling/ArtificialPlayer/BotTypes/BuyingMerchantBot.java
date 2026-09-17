package soloMapling.ArtificialPlayer.BotTypes;

import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotTradeSystem.BotTradeSM;
import soloMapling.FreeMarket.FMItem;
import soloMapling.FreeMarket.MarketBotAmbient;
import soloMapling.FreeMarket.MarketBotFlavor;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.MarketBotDirector;

import java.util.Collections;
import java.util.List;
import java.util.function.Supplier;

import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotEmote;
import static soloMapling.ArtificialPlayer.BotTypeManager.BotType.NX_MERCHANT_BOT;
import static soloMapling.ArtificialPlayer.BotTypeManager.convertBotType;
import static soloMapling.BotLogger.log;
import static soloMapling.Environment.EnvironmentManager.botMoveToPlatformAnyUnoccupiedSpot;
import static soloMapling.Environment.EnvironmentManager.getCurrentPlatform;
import static soloMapling.Environment.EnvironmentManager.getMainPlatformIds;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateDarkScrollsList;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateScrollsList;
import static soloMapling.FreeMarket.FMEconomyManager.formatPriceToShorthand;
import static soloMapling.FreeMarket.FMEconomyManager.priceAdjustmentRules;
import static soloMapling.itemPool.ItemInformationProviderUtilities.getItemName;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.isBotMoving;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.nudgeAwayFromOverlap;
import static soloMapling.server.SoloMaplingUtilities.getRandomElement;
import static soloMapling.server.SoloMaplingUtilities.random;
import static soloMapling.server.SoloMaplingUtilities.rollChanceInverse;

public class BuyingMerchantBot extends BotSM {
    private BuyingState buyingState = BuyingState.RESET;
    private List<String> hint = Collections.singletonList(getChr().getName());
    private List<FMItem> itemsToBuy;
    private int itemIndex = 0;
    private boolean movedDuringAdvertise = false;

    private static final double BUY_DISCOUNT_MIN = 0.80;
    private static final double BUY_DISCOUNT_MAX = 0.90;

    private enum BuyingState {
        RESET,
        SELECT_ITEM,
        ADVERTISE,
        CHECK_TRADES,
        IDLE_ACTIONS
    }

    private static final List<String> FLAVOR_NODES = List.of("ScamMessages", "BeggingMessages", "RWTMessages", "FunnyMessages");

    public BuyingMerchantBot(Character character) {
        super(character);
        dialoguePath = "MerchantBotDialogue.yaml";
        botType = "MerchantBot";
    }

    @Override
    public boolean usesSharedMarketTick() {
        return true;
    }

    private void resetState() {
        itemIndex = 0;
        loadItemList();
        buyingState = BuyingState.RESET;
    }

    private void loadItemList() {
        Supplier<List<FMItem>>[] generators = new Supplier[]{
                () -> generateScrollsList("A"),
                () -> generateDarkScrollsList("A")
        };
        itemsToBuy = generators[random.nextInt(generators.length)].get();
    }

    private FMItem getCurrentItem() {
        if (itemsToBuy == null || itemIndex >= itemsToBuy.size()) {
            return null;
        }
        return itemsToBuy.get(itemIndex);
    }

    private void selectNextItem() {
        if (itemsToBuy == null || itemsToBuy.isEmpty()) {
            loadItemList();
        }

        itemIndex++;
        if (itemIndex >= itemsToBuy.size()) {
            itemIndex = 0;
            loadItemList();
        }

        FMItem currItem = getCurrentItem();
        if (currItem == null) {
            return;
        }

        // Set up buying mode: we want the item, we offer mesos at a discount
        setTradeMode(BotTradeSM.TradeMode.BUYING);
        getTradeWants().resetTradeWants();
        getTradeWants().addItemWanted(currItem.getItemId(), 1);

        int marketPrice = currItem.getPrice();
        double discount = BUY_DISCOUNT_MIN + random.nextDouble() * (BUY_DISCOUNT_MAX - BUY_DISCOUNT_MIN);
        int buyPrice = priceAdjustmentRules((int) (marketPrice * discount));
        getTradeWants().setMesoOffering(buyPrice);
        getTradeWants().setMesoWanted(0);

        resetLastTradeResult();
        resetLastTradedCharacter();
    }

    private void advertise() {
        FMItem itm = getCurrentItem();
        if (itm == null) {
            return;
        }
        String itemName = getItemName(itm.getItemId());
        if (itemName != null && random.nextInt(100) < 72 && MarketBotDirector.get().trySpeak(getChr())) {
            String msg = buildBuyingMessage(itemName, getTradeWants().getMesoOffering());
            SocialCommands.BotSpeak(getChr(), msg);
        }
    }

    static String buildBuyingMessage(String itemName, int offerPrice) {
        return MarketBotFlavor.buying(itemName, formatPriceToShorthand(offerPrice));
    }

    private boolean tryPlatformShuffleWhileAdvertising() {
        if (!SoloMaplingConfig.marketWanderEnabled()) {
            return false;
        }
        Runnable move = null;
        if (rollChanceInverse(10)) {
            move = () -> {
                botMoveToPlatformAnyUnoccupiedSpot(getChr(), getCurrentPlatform(getChr()));
                if (rollChanceInverse(2)) nudgeAwayFromOverlap(getChr());
            };
        } else if (rollChanceInverse(20)) {
            move = () -> {
                botMoveToPlatformAnyUnoccupiedSpot(getChr(), getRandomElement(List.of("m1", "m5")));
                if (rollChanceInverse(2)) nudgeAwayFromOverlap(getChr());
            };
        }
        return move != null && MarketBotDirector.get().runPathfind(move);
    }

    private void handleIdleActions() {
        MarketBotAmbient.act(this);
    }

    private boolean tryConvertToNXMerchant() {
        if (rollChanceInverse(100)) {
            convertBotType(getChr(), NX_MERCHANT_BOT);
            return true;
        }
        return false;
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
        if (MarketBotAmbient.isSitting(getChr()) || isBusy() || isBotMoving(getChr())) {
            if (MarketBotAmbient.isSitting(getChr()) && SoloMaplingConfig.marketHawkEnabled()) {
                advertise();
            }
            return;
        }
        getDebugger().debugLoggingFull(
                String.format("%s BuyingMerchantBot: %s", getChr().getName(), buyingState),
                String.format("%s", buyingState));

        switch (buyingState) {
            case RESET:
                resetState();
                buyingState = BuyingState.SELECT_ITEM;
                break;
            case SELECT_ITEM:
                selectNextItem();
                buyingState = BuyingState.ADVERTISE;
                break;
            case ADVERTISE:
                if (SoloMaplingConfig.marketHawkEnabled()) {
                    advertise();
                }
                movedDuringAdvertise = false;
                buyingState = BuyingState.CHECK_TRADES;
                busyFor(400);
                break;
            case CHECK_TRADES:
                checkForTrades();
                buyingState = BuyingState.IDLE_ACTIONS;
                break;
            case IDLE_ACTIONS:
                if (tryConvertToNXMerchant()) {
                    return;
                }
                buyingState = BuyingState.SELECT_ITEM;
                break;
            default:
                log("Unexpected state: " + buyingState);
                state = BotState.FINISHED;
                throw new IllegalStateException("Unexpected state: " + buyingState);
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
