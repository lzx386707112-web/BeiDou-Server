package soloMapling.ArtificialPlayer.BotTypes;

import org.gms.client.Character;
import org.gms.client.inventory.Item;
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
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateItem;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generatePotionsList;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateScrollsList;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateThiefStarsList;
import static soloMapling.FreeMarket.FMEconomyManager.priceAdjustmentRules;
import static soloMapling.itemPool.ItemInformationProviderUtilities.getItemName;
import static soloMapling.itemPool.ItemUtilities.getItemMarketValue;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.isBotMoving;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.nudgeAwayFromOverlap;
import static soloMapling.server.SoloMaplingUtilities.getRandomElement;
import static soloMapling.server.SoloMaplingUtilities.random;
import static soloMapling.server.SoloMaplingUtilities.rollChanceInverse;

public class SellingMerchantBot extends BotSM {
    private SellingState sellingState = SellingState.RESET;
    private List<String> hint = Collections.singletonList(getChr().getName());
    private List<FMItem> itemsToSell;
    private int itemIndex = 0;
    private boolean movedDuringAdvertise = false;

    private enum SellingState {
        RESET,
        SELECT_ITEM,
        ADVERTISE,
        CHECK_TRADES,
        IDLE_ACTIONS
    }

    private static final List<String> FLAVOR_NODES = List.of("ScamMessages", "BeggingMessages", "RWTMessages", "FunnyMessages");

    public SellingMerchantBot(Character character) {
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
        sellingState = SellingState.RESET;
    }

    private void loadItemList() {
        Supplier<List<FMItem>>[] generators = new Supplier[]{
                () -> generateScrollsList("A"),
                () -> generateDarkScrollsList("A"),
                () -> generateThiefStarsList("A"),
                () -> generatePotionsList("S")
        };
        itemsToSell = generators[random.nextInt(generators.length)].get();
        if (itemsToSell == null || itemsToSell.isEmpty()) {
            itemsToSell = generatePotionsList("S");
        }
        if (itemsToSell == null || itemsToSell.isEmpty()) {
            itemsToSell = List.of(new FMItem(2000002, 1, 100), new FMItem(2000001, 1, 100));
        }
    }

    private FMItem getCurrentItem() {
        if (itemsToSell == null || itemIndex >= itemsToSell.size()) {
            return null;
        }
        return itemsToSell.get(itemIndex);
    }

    private void selectNextItem() {
        if (itemsToSell == null || itemsToSell.isEmpty()) {
            loadItemList();
        }
        if (itemsToSell == null || itemsToSell.isEmpty()) {
            return;
        }

        itemIndex++;
        if (itemIndex >= itemsToSell.size()) {
            itemIndex = 0;
            loadItemList();
        }

        FMItem currItem = getCurrentItem();
        if (currItem == null) {
            return;
        }

        Item item = generateItem(currItem.getItemId(), 1, 1);
        getTradeInventory().setItemForSaleMain(item);
        getTradeWants().resetTradeWants();
        int rawValue = getItemMarketValue(item);
        int adjValue = priceAdjustmentRules((int) (rawValue * 0.9));
        getTradeWants().setMesoWanted(adjValue);
        setTradeMode(BotTradeSM.TradeMode.SELLING);

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
            String msg = buildSellingMessage(itemName);
            SocialCommands.BotSpeak(getChr(), msg);
        }
    }

    static String buildSellingMessage(String itemName) {
        return MarketBotFlavor.selling(itemName);
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
        } else if (rollChanceInverse(30)) {
            move = () -> {
                botMoveToPlatformAnyUnoccupiedSpot(getChr(), getRandomElement(List.of("m1", "m2")));
                if (rollChanceInverse(2)) nudgeAwayFromOverlap(getChr());
            };
        } else if (rollChanceInverse(70)) {
            int currentMap = getChr().getMapId();
            move = () -> {
                botMoveToPlatformAnyUnoccupiedSpot(getChr(), getRandomElement(getMainPlatformIds(currentMap)));
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
                String.format("%s SellingMerchantBot: %s", getChr().getName(), sellingState),
                String.format("%s", sellingState));

        switch (sellingState) {
            case RESET:
                resetState();
                sellingState = SellingState.SELECT_ITEM;
                break;
            case SELECT_ITEM:
                selectNextItem();
                sellingState = SellingState.ADVERTISE;
                break;
            case ADVERTISE:
                if (SoloMaplingConfig.marketHawkEnabled()) {
                    advertise();
                }
                movedDuringAdvertise = false;
                sellingState = SellingState.CHECK_TRADES;
                busyFor(400);
                break;
            case CHECK_TRADES:
                checkForTrades();
                sellingState = SellingState.IDLE_ACTIONS;
                break;
            case IDLE_ACTIONS:
                if (tryConvertToNXMerchant()) {
                    return;
                }
                sellingState = SellingState.SELECT_ITEM;
                break;
            default:
                log("Unexpected state: " + sellingState);
                state = BotState.FINISHED;
                throw new IllegalStateException("Unexpected state: " + sellingState);
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
