package org.gms.client.command.commands.gm4;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.client.command.Command;
import org.gms.server.maps.Portal;
import soloMapling.ArtificialPlayer.BotHelpers;
import soloMapling.ArtificialPlayer.BotClientHandler;
import soloMapling.ArtificialPlayer.BotTypeManager;
import soloMapling.ArtificialPlayer.ConversationManager;
import soloMapling.ArtificialPlayer.SocialHotPotatoManager;
import soloMapling.Casino.CasinoChipConfig;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.ExecutorServiceManager;
import soloMapling.server.NpcSpawner;

import java.awt.Point;

import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotSpeak;
import static soloMapling.DebugUtilities.debugprint;
import static soloMapling.Environment.EnvironmentManager.botMoveToPlatformAnyUnoccupiedSpot;
import static soloMapling.Environment.EnvironmentManager.environmentLoadStartup;
import static soloMapling.Environment.EnvironmentManager.getAllCharsOnPlatform;
import static soloMapling.Environment.EnvironmentManager.getAvailablePlatformIds;
import static soloMapling.Environment.EnvironmentManager.getCurrentPlatform;
import static soloMapling.Environment.EnvironmentManager.getMainPlatformIds;
import static soloMapling.Environment.EnvironmentManager.spawnBotsInFMEntrance;
import static soloMapling.Environment.EnvironmentManager.spawnCasinoNpcs;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBots;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBotsHenesys;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBotsHenesysMarket;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBotsHenesysPark;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBotsGameZone;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBotsLockedY;
import static soloMapling.Environment.EnvironmentManager.spawnFillerBotsPotionShop;
import static soloMapling.Environment.EnvironmentManager.convertRandomFillersToScrollBots;
import static soloMapling.Environment.EnvironmentManager.spawnOPQBotsInLobby;
import static soloMapling.Environment.EnvironmentManager.spawnGameZoneHostBots;
import static soloMapling.Environment.EnvironmentManager.spawnBlackjackTables;
import static soloMapling.Environment.EnvironmentManager.spawnGachaBotsHenesys;
import static soloMapling.Environment.EnvironmentManager.spawnHenesysBots;
import static soloMapling.Environment.EnvironmentManager.spawnMerchBotsInFMEntrance;
import static soloMapling.server.SoloMaplingUtilities.getRandomElement;
import static soloMapling.server.SoloMaplingUtilities.isInteger;

public class EnvironmentCommand extends Command {
    {
        setDescription("Environment Commands.");
    }

    private static Character player;
    
    @Override
    public void execute(Client c, String[] params) {
        BotClientHandler.createBotClient(c);
        player = c.getPlayer();
        if (params.length == 0) {
            ExecutorServiceManager.getExecutorService().execute(() -> {
                player.yellowMessage("No Command Parameter Found. Try !env help");
            });
            return;
        }
        if (params.length == 1) {
            ExecutorServiceManager.getExecutorService().execute(() ->
            {
                handleSingleInputCommand(params[0], c);
            });
            return;
        }
        if (params.length == 2) {
            ExecutorServiceManager.getExecutorService().execute(() ->
            {
                if (isInteger(params[1])) {
                    int commandNum = Integer.parseInt(params[1]);
                    handleStringIntCommand(params[0], commandNum, c);
                } else if (!isInteger(params[0]) && !isInteger(params[1])) {
                    String commandString1 = (params[0]);
                    String commandString2 = params[1];
                    handleStringStringCommand(commandString1, commandString2, c);
                } else {
                    player.yellowMessage("Second input not an integer");
                }
            });
            return;
        }
        if (params.length == 3) {
            ExecutorServiceManager.getExecutorService().execute(() ->
            {
                if (isInteger(params[1]) && isInteger(params[2])) {
                    int commandNum = Integer.parseInt(params[1]);
                    int commandNum2 = Integer.parseInt(params[2]);
                    handleStringIntIntCommand(params[0], commandNum, commandNum2, c);
                } else if (isInteger(params[1])) {
                    int commandNum = Integer.parseInt(params[1]);
                    String commandString = params[2];
                    handleStringIntStringCommand(params[0], commandNum, commandString);
                } else {
                    player.yellowMessage("Second input not an integer");
                }
            });
            return;
        }
    }

    public static void handleSingleInputCommand(String input, Client c) {
        switch (input.toLowerCase()) {
            case "help":
                printHelp();
                break;
            case "loadenv":
                if (!requireFeature(SoloMaplingConfig.autoEnvironmentEnabled(), "完整 SoloMapling 大环境自动加载")) return;
                environmentLoadStartup();
                break;
            case "spawnfmbots":
                if (!requireFeature(SoloMaplingConfig.fmBotsEnabled(), "FM 假人")) return;
                spawnBotsInFMEntrance();
                break;
            case "spawnmerchantbots":
            case "spawnmerchbots":
                if (!requireFeature(SoloMaplingConfig.fmMerchantsEnabled(), "FM 商人")) return;
                spawnMerchBotsInFMEntrance();
                break;
            case "spawnhenesysbots":
                if (!requireFeature(SoloMaplingConfig.henesysCrowdEnabled()
                        || SoloMaplingConfig.henesysMarketCrowdEnabled()
                        || SoloMaplingConfig.henesysParkCrowdEnabled(), "射手村人群")) return;
                spawnHenesysBots();
                break;
            case "spawngachabots":
                if (!requireFeature(SoloMaplingConfig.gachaBotsEnabled(), "扭蛋假人")) return;
                spawnGachaBotsHenesys();
                break;
            case "getmap":
                debugprint("Current Map:", c.getPlayer().getMapId());
                break;
            case "getportal":
                // From !debug portal
                Portal portal = player.getMap().findClosestPortal(player.getPosition());
                if (portal != null) {
                    player.dropMessage(6, "Closest portal: id: " + portal.getId() + " name: '" + portal.getName() + "' Type: " + portal.getType() + " --> toMap: " + portal.getTargetMapId() + "' state: " + (portal.getPortalState() ? 1 : 0) + ", Pos: " +
                            portal.getPosition());
                } else {
                    player.dropMessage(6, "There is no portal on this map.");
                }
                break;
            case "getplat":
            case "getplatform":
            case "getcurrentplat":
            case "getcurrentplatform":
                System.out.println(getCurrentPlatform(c.getPlayer()));
                break;
            case "getallplatforms":
                System.out.println(getAvailablePlatformIds(c.getPlayer().getMapId()));
                break;
            case "getallmainplatforms":
                System.out.println(getMainPlatformIds((c.getPlayer().getMapId())));
                break;
            case "spawnhenefillers":
                if (!requireFeature(SoloMaplingConfig.henesysCrowdEnabled(), "射手村人群")) return;
                player.yellowMessage("Spawning Henesys filler bots...");
                spawnFillerBotsHenesys();
                player.yellowMessage("Henesys filler bots done.");
                break;
            case "spawnmarketfillers":
                if (!requireFeature(SoloMaplingConfig.henesysMarketCrowdEnabled(), "射手村市场人群")) return;
                player.yellowMessage("Spawning Henesys Market filler bots...");
                spawnFillerBotsHenesysMarket();
                player.yellowMessage("Henesys Market filler bots done.");
                break;
            case "spawnparkfillers":
                if (!requireFeature(SoloMaplingConfig.henesysParkCrowdEnabled(), "射手村公园人群")) return;
                player.yellowMessage("Spawning Henesys Park filler bots...");
                spawnFillerBotsHenesysPark();
                player.yellowMessage("Henesys Park filler bots done.");
                break;
            case "spawngamezonefillers":
                if (!requireFeature(SoloMaplingConfig.henesysGameZoneCrowdEnabled(), "游戏区人群")) return;
                player.yellowMessage("Spawning Game Zone filler bots...");
                spawnFillerBotsGameZone();
                player.yellowMessage("Game Zone filler bots done.");
                break;
            case "spawnpotshopfillers":
                if (!requireFeature(SoloMaplingConfig.henesysPotionShopCrowdEnabled(), "药店人群")) return;
                player.yellowMessage("Spawning Potion Shop filler bots...");
                spawnFillerBotsPotionShop();
                player.yellowMessage("Potion Shop filler bots done.");
                break;
            case "spawnallfillers":
                player.yellowMessage("Spawning all filler bots...");
                spawnFillerBotsHenesys();
                spawnFillerBotsHenesysMarket();
                spawnFillerBotsHenesysPark();
                spawnFillerBotsGameZone();
                spawnFillerBotsPotionShop();
                player.yellowMessage("All filler bots done.");
                break;
            case "convertscrollbots":
                if (!requireFeature(SoloMaplingConfig.scrollBotsEnabled(), "卷轴假人转换")) return;
                player.yellowMessage("Converting random fillers to Scroll Bots...");
                convertRandomFillersToScrollBots();
                player.yellowMessage("Scroll Bot conversion done.");
                break;
            case "spawnopqbots":
                if (!requireFeature(SoloMaplingConfig.opqLobbyBotsEnabled(), "OPQ lobby 假人")) return;
                player.yellowMessage("Spawning OPQ bots in lobby...");
                spawnOPQBotsInLobby();
                player.yellowMessage("OPQ lobby bots done.");
                break;
            case "spawngzhbots":
                if (!requireFeature(SoloMaplingConfig.gameZoneHostBotsEnabled(), "游戏区主持假人")) return;
                player.yellowMessage("Spawning Game Zone Host Bots...");
                spawnGameZoneHostBots();
                player.yellowMessage("Game Zone Host Bots done.");
                break;
            case "spawnbjtables":
                if (!requireFeature(SoloMaplingConfig.blackjackTablesEnabled(), "21点桌")) return;
                player.yellowMessage("Spawning Blackjack Tables...");
                spawnBlackjackTables();
                player.yellowMessage("Blackjack Tables done.");
                break;
            case "starthotpotato":
                if (!requireFeature(SoloMaplingConfig.hotPotatoEnabled(), "Hot Potato 社交系统")) return;
                SocialHotPotatoManager.getInstance().start();
                player.yellowMessage("Social Hot Potato started.");
                break;
            case "stophotpotato":
                SocialHotPotatoManager.getInstance().stop();
                player.yellowMessage("Social Hot Potato stopped.");
                break;
            case "startconvo":
                if (!requireFeature(SoloMaplingConfig.conversationEnabled(), "对话系统")) return;
                ConversationManager.getInstance().start();
                player.yellowMessage("Conversation Manager started.");
                break;
            case "stopconvo":
                ConversationManager.getInstance().stop();
                player.yellowMessage("Conversation Manager stopped.");
                break;
            case "spawncasinonpc":
                if (!requireFeature(SoloMaplingConfig.casinoNpcEnabled(), "赌场 NPC")) return;
                spawnCasinoNpc(c);
                break;
            case "spawnrpsnpc":
                if (!requireFeature(SoloMaplingConfig.rpsNpcEnabled(), "猜拳 NPC")) return;
                NpcSpawner.spawnNpcAtPlayer(c.getPlayer(), 9000019);
                break;
            case "spawncasinonpcs":
                if (!requireFeature(SoloMaplingConfig.casinoNpcEnabled() || SoloMaplingConfig.rpsNpcEnabled(), "赌场/猜拳 NPC")) return;
                spawnCasinoNpcs();
                player.yellowMessage("Casino NPCs spawned on map 100000203.");
                break;
            default:
                player.yellowMessage("Invalid command - Direct Command");
                break;
        }
    }

    private static boolean requireFeature(boolean enabled, String featureName) {
        if (enabled) {
            return true;
        }
        player.yellowMessage(featureName + " 已在后台参数中关闭。");
        return false;
    }

    public static void handleStringIntIntCommand(String input, int input2, int input3, Client c) {
        Character fakechar = BotHelpers.getCharFromChannelStorage(input2);
        if (fakechar == null) {
            player.yellowMessage("Bot null");
            return;
        }

        player.yellowMessage("Command: " + input2 + ", arg: " + input3);
        switch (input.toLowerCase()) {
            default:
                player.yellowMessage("Invalid command - handleStringIntIntCommand");
                break;
        }
    }

    public static void handleStringIntCommand(String input, int input2, Client c) {
        switch (input.toLowerCase()) {
            case "fillerbot":
                Point p1 = new Point(-548, 154);
                Point p2 = new Point(568, 154);
                int mapId = player.getMapId();
                player.yellowMessage("Spawning " + input2 + " filler bots on map " + mapId);
                java.util.List<Integer> fillerIds = spawnFillerBots(input2, mapId, p1, p2);
                BotTypeManager.setAndStartBots(fillerIds, BotTypeManager.BotType.SOCIAL_BOT);
                player.yellowMessage("Filler bot spawn complete. " + fillerIds.size() + " SocialBots assigned.");
                return;
            case "fillerboty":
                Point p1a = new Point(-112, -127);
                Point p2a = new Point(245, -127);

                int mapIdy = player.getMapId();
                player.yellowMessage("Spawning " + input2 + " filler bots on map " + mapIdy);
                java.util.List<Integer> fillerIdsY = spawnFillerBotsLockedY(input2, mapIdy, p1a, p2a);
                BotTypeManager.setAndStartBots(fillerIdsY, BotTypeManager.BotType.SOCIAL_BOT);
                player.yellowMessage("Filler bot spawn complete. " + fillerIdsY.size() + " SocialBots assigned.");
                break;
            default:
                break;
        }

        Character fakechar = BotHelpers.getCharFromChannelStorage(input2);
        if (fakechar == null) {
            player.yellowMessage("Bot null for handleStringIntCommand");
            return;
        }

        switch (input.toLowerCase()) {
            default:
                player.yellowMessage("Invalid command - handleStringIntCommand");
                break;
        }
    }

    public static void handleStringStringCommand(String input, String input2, Client c) {
        switch (input.toLowerCase()) {
            case "Test":
                break;
            case "getallcharsonplatform":
            case "getcharsonplatform":
                getAllCharsOnPlatform(c.getPlayer().getMapId(), input2);
                break;
            default:
                player.yellowMessage("Invalid command - handleStringIntCommand");
                break;
        }
    }

    public static void handleStringIntStringCommand(String input, int input2, String str) {
        Character fakechar = BotHelpers.getCharFromChannelStorage(input2);
        if (fakechar == null) {
            player.yellowMessage("Bot null");
            return;
        }

        switch (input.toLowerCase()) {
            case "chat":
                BotSpeak(fakechar, str);
                break;
            case "platformshuffle":
                botMoveToPlatformAnyUnoccupiedSpot(fakechar, str);
                break;
            case "platformshufflerandom":
                int currentMap = fakechar.getMapId();
                botMoveToPlatformAnyUnoccupiedSpot(fakechar, getRandomElement(getMainPlatformIds(currentMap)));
                break;
            default:
                player.yellowMessage("Invalid command Two Object");
                break;
        }

    }

    private static void printHelp() {
        player.yellowMessage("---- Environment Commands (!env) ----");
        player.yellowMessage("-- World Startup --");
        player.yellowMessage("!env loadenv                     - run full environment startup");
        player.yellowMessage("-- FM Spawning --");
        player.yellowMessage("!env spawnfmbots                 - spawn FM entrance bots");
        player.yellowMessage("!env spawnmerchbots              - spawn merchant bots in FM entrance");
        player.yellowMessage("-- Henesys Spawning --");
        player.yellowMessage("!env spawnhenesysbots            - spawn Henesys wanderer bots");
        player.yellowMessage("!env spawngachabots              - spawn gacha bots in Henesys");
        player.yellowMessage("-- Filler Bots --");
        player.yellowMessage("!env spawnhenefillers            - spawn Henesys filler bots");
        player.yellowMessage("!env spawnmarketfillers          - spawn Henesys Market fillers");
        player.yellowMessage("!env spawnparkfillers            - spawn Henesys Park fillers");
        player.yellowMessage("!env spawngamezonefillers        - spawn Game Zone fillers");
        player.yellowMessage("!env spawnpotshopfillers         - spawn Potion Shop fillers");
        player.yellowMessage("!env spawnallfillers             - spawn all filler bots");
        player.yellowMessage("!env fillerbot <count>           - spawn N fillers at fixed X coords");
        player.yellowMessage("!env fillerboty <count>          - spawn N fillers at fixed Y coords");
        player.yellowMessage("!env convertscrollbots           - convert random fillers to scroll bots");
        player.yellowMessage("-- Special Spawns --");
        player.yellowMessage("!env spawnopqbots                - spawn OPQ lobby bots");
        player.yellowMessage("!env spawngzhbots                - spawn Game Zone Host bots");
        player.yellowMessage("!env spawnbjtables               - spawn Blackjack tables");
        player.yellowMessage("!env spawncasinonpc              - spawn casino NPC at player");
        player.yellowMessage("!env spawncasinonpcs             - spawn all casino NPCs on map");
        player.yellowMessage("!env spawnrpsnpc                 - spawn RPS NPC");
        player.yellowMessage("-- Social Systems --");
        player.yellowMessage("!env starthotpotato              - start Social Hot Potato manager");
        player.yellowMessage("!env stophotpotato               - stop Social Hot Potato manager");
        player.yellowMessage("!env startconvo                  - start Conversation Manager");
        player.yellowMessage("!env stopconvo                   - stop Conversation Manager");
        player.yellowMessage("-- Map Inspection --");
        player.yellowMessage("!env getmap                      - get current map ID");
        player.yellowMessage("!env getportal                   - get closest portal info");
        player.yellowMessage("!env getplatform                 - get current platform");
        player.yellowMessage("!env getallplatforms             - get all available platforms");
        player.yellowMessage("!env getallmainplatforms         - get all main platforms");
        player.yellowMessage("!env getcharsonplatform <platId> - get chars on a platform");
        player.yellowMessage("-- Bot Control --");
        player.yellowMessage("!env chat <cid> <message>        - bot speaks in chat");
        player.yellowMessage("!env platformshuffle <cid> <id>  - move bot to platform");
        player.yellowMessage("!env platformshufflerandom <cid> - move bot to random platform");
    }

    private static void spawnCasinoNpc(Client c) {
        NpcSpawner.spawnNpcAtPlayer(c.getPlayer(), CasinoChipConfig.CASINO_NPC_ID);
    }

}
