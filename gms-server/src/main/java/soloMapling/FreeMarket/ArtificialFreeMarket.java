package soloMapling.FreeMarket;

import org.gms.client.Client;
import org.gms.client.Character;
import org.gms.client.Job;
import org.gms.client.inventory.Item;
import org.gms.net.server.Server;
import org.gms.net.server.channel.Channel;
import org.gms.net.server.world.World;
import org.gms.server.maps.HiredMerchant;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.PlayerShop;
import org.gms.server.maps.PlayerShopItem;
import soloMapling.ArtificialPlayer.BotClientHandler;
import soloMapling.Environment.PlatformSpawner;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.ExecutorServiceManager;
import org.gms.util.PacketCreator;

import java.awt.*;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static soloMapling.ArtificialPlayer.BotCustomization.getRandomChairId;
import static soloMapling.ArtificialPlayer.BotCustomization.getRandomStorePermitId;
import soloMapling.ArtificialPlayer.BotGeneration;

import static soloMapling.ArtificialPlayer.BotGeneration.createBotPollReadiness;
import static soloMapling.server.ExecutorServiceManager.runAsync;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botSitChair;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.microTurnAround;
import static soloMapling.DebugUtilities.debugprint;
import static soloMapling.FreeMarket.ArtificialShopGenerator.applyAdditionalShopMods;
import static soloMapling.FreeMarket.ArtificialShopGenerator.applyCheapSaleDiscount;
import static soloMapling.FreeMarket.ArtificialShopGenerator.applyQuittingSaleDiscount;
import static soloMapling.FreeMarket.ArtificialShopGenerator.buyoutSomeItems;
import static soloMapling.FreeMarket.ArtificialShopGenerator.setOneMesoShop;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateShop;
import static soloMapling.FreeMarket.ArtificialShopGenerator.generateSecondaryShop;

import static soloMapling.FreeMarket.FMEconomyManager.getTierForRoom;
import static soloMapling.FreeMarket.FMEconomyManager.isHotRoom;
import static soloMapling.FreeMarket.FMShopTypeManager.selectHotRoomShopType;
import static soloMapling.FreeMarket.FMShopDescriptionManager.appendRoomNumber;
import static soloMapling.FreeMarket.FMShopDescGen.getRandomShopOwnerIGN;
import static soloMapling.FreeMarket.FMShopDescriptionManager.setMerchantDescription;
import static soloMapling.FreeMarket.FMShopDescriptionManager.appendMerchantDescription;
import static soloMapling.FreeMarket.FMShopInfoManager.getRegionByMapId;
import static soloMapling.FreeMarket.FMShopTypeManager.getSecondaryShopItemTypes;
import static soloMapling.FreeMarket.FMShopTypeManager.selectShopTypeWeightedProbability;

import static soloMapling.FreeMarket.HiredMerchantArtificial.shopTypes.*;
import static soloMapling.server.ExecutorServiceManager.getExecutorService;
import static soloMapling.server.ExecutorServiceManager.getScheduledExecutorService;
import static soloMapling.server.SoloMaplingUtilities.chance;

public class ArtificialFreeMarket {

    static final List<Integer> hiredMerchantsList = FMShopInfoManager.hiredMerchantItemIds;
    private static final Random random = new Random();
    private static final AtomicInteger marketShopCount = new AtomicInteger(0);
    private static final AtomicInteger nextMerchantOwnerId = new AtomicInteger(800001);
    private static final ConcurrentHashMap<String, AtomicInteger> shopsByMap = new ConcurrentHashMap<>();
    public static FMShopInfoManager fmInfo = new FMShopInfoManager();
    private record ShopSpot(int mapId, Point position) {}

    public static void populateFreeMarketSpot(Client c) {
        if (!SoloMaplingConfig.fmRegionFillEnabled()) {
            debugprint("Free Market spot fill disabled by config.");
            return;
        }
        spawnHiredMerchantStore(c.getPlayer().getMapId(), c.getPlayer().getPosition());
    }

    public static void populateFreeMarketFull() {
        if (!SoloMaplingConfig.fmRegionFillEnabled()) {
            debugprint("Free Market full fill disabled by config.");
            return;
        }
        List<String> regions = List.of("henesys", "ludi", "perion", "elnath");
        for (String region : regions) {
            populateFreeMarketRegion(region);
        }
    }


    public static void populateFreeMarketRegion(String region) {
        if (!SoloMaplingConfig.fmRegionFillEnabled()) {
            debugprint("Free Market region fill disabled by config: " + region);
            return;
        }
        int perRoom = SoloMaplingConfig.marketShopMax();
        for (int mapId : fmInfo.getRegionFMMapId(region)) {
            List<Point> spots = new java.util.ArrayList<>(fmInfo.getRegionFMSpots(region));
            Collections.shuffle(spots, random);
            int spawned = 0;
            for (Point position : spots) {
                if (spawned >= perRoom) {
                    break;
                }
                if (spawnHiredMerchantStore(mapId, position)) {
                    spawned++;
                }
            }
        }
        debugprint("Free Market shops populated: " + marketShopCount.get());
    }

    public static void populateFreeMarketEntrance() {
        MarketBotLog.info("skip hired merchants at FM entrance; shops only in rooms 910000001-012");
    }

    public static void populateHenesysLayoutRooms(int fromMapId, int toMapId) {
        populateMarketRooms(fromMapId, toMapId);
    }

    public static void populateMarketRooms(int fromMapId, int toMapId) {
        if (!SoloMaplingConfig.fmRegionFillEnabled()) {
            MarketBotLog.warn("populateMarketRooms skipped; fmRegionFill disabled");
            return;
        }
        MarketBotLog.info("populateMarketRooms {}-{}", fromMapId, toMapId);
        for (int mapId = fromMapId; mapId <= toMapId; mapId++) {
            String region = getRegionByMapId(mapId);
            List<Point> spots;
            try {
                spots = fmInfo.getRegionFMSpots(region);
            } catch (IllegalArgumentException ignored) {
                spots = FMShopInfoManager.henesysShopCoordinates;
            }
            spawnShopsOnMap(mapId, spots, spots.size());
            spawnVisibleShopkeepers(mapId, spots, 2);
        }
    }

    private static void spawnShopsOnMap(int mapId, List<Point> sourceSpots, int cap) {
        List<Point> spots = new java.util.ArrayList<>(sourceSpots);
        Collections.shuffle(spots, random);
        int spawned = 0;
        for (Point position : spots) {
            if (spawned >= cap) {
                break;
            }
            if (spawnHiredMerchantStore(mapId, position)) {
                spawned++;
            }
        }
        System.out.println("[ArtificialFreeMarket] hired merchants on " + mapId + ": " + spawned + "/" + Math.min(cap, spots.size()));
        MarketBotLog.info("hired merchants map={} spawned={}/{}", mapId, spawned, Math.min(cap, spots.size()));
    }

    private static void spawnVisibleShopkeepers(int mapId, List<Point> sourceSpots, int count) {
        List<Point> spots = new java.util.ArrayList<>(sourceSpots);
        Collections.shuffle(spots, random);
        int spawned = 0;
        for (Point position : spots) {
            if (spawned >= count) {
                break;
            }
            createBotShopAtLocation(position, mapId);
            spawned++;
        }
        MarketBotLog.info("shopkeepers queued map={} count={}", mapId, spawned);
    }

    public static void populateFreeMarketRoom(int mapId) {
        if (!SoloMaplingConfig.fmRegionFillEnabled()) {
            debugprint("Free Market room fill disabled by config: " + mapId);
            return;
        }
        String region = getRegionByMapId(mapId);
        debugprint("Populating room: ", mapId);

        List<Point> positions = fmInfo.getRegionFMSpots(region);
        AtomicInteger delayCounter = new AtomicInteger(0);

        double hiredMerchantChance = getHiredMerchantChance(mapId);

        for (Point position : positions) {
            // ~2% per-spot skip. Use continue so we don't abandon the rest of the room.
            if (chance(2)) {
                continue;
            }
            if (Math.random() < hiredMerchantChance) {
                ExecutorServiceManager.runAsync(() -> spawnHiredMerchantStore(mapId, position));
            } else {
                // Stagger bot-shop creation with small delays instead of blocking
                int delay = delayCounter.getAndIncrement() * 200; // 200ms between each
                getScheduledExecutorService().schedule(() -> createBotShopAtLocation(position, mapId),
                        delay, TimeUnit.MILLISECONDS);
            }
        }
    }

//    public static void populateFreeMarket(String region, int mapId) {
//        for (Point position : fmInfo.getRegionFMSpots(region)) {
//            ExecutorServiceManager.getExecutorService().execute(() ->
//                    spawnHiredMerchantStore(mapId, position));
//        }
//    }


    private static boolean spawnHiredMerchantStore(int mapId, Point position) {
        if (mapId == 910000000) {
            return false;
        }
        boolean any = false;
        for (Channel channel : marketChannels()) {
            if (spawnHiredMerchantStoreOnChannel(channel, mapId, position)) {
                any = true;
            }
        }
        return any;
    }

    private static List<Channel> marketChannels() {
        Client source = BotClientHandler.ensureStandaloneClient();
        World world = Server.getInstance().getWorld(source.getWorld());
        if (world != null && world.getChannels() != null && !world.getChannels().isEmpty()) {
            return world.getChannels();
        }
        Channel fallback = Server.getInstance().getChannel(source.getWorld(), source.getChannel());
        return fallback == null ? List.of() : List.of(fallback);
    }

    private static boolean spawnHiredMerchantStoreOnChannel(Channel channel, int mapId, Point position) {
        if (channel == null) {
            return false;
        }
        if (!reserveMarketShopSlot(channel.getId(), mapId)) {
            return false;
        }
        if (calculateSkippedSpot(mapId)) {
            releaseMarketShopSlot(channel.getId(), mapId);
            return false;
        }
        try {
            MapleMap map = channel.getMapFactory().getMap(mapId);
            Point grounded = PlatformSpawner.snapToGround(map, position);
            if (grounded == null) {
                grounded = new Point(position);
            }

            int ownerId = nextMerchantOwnerId.getAndIncrement();
            String ownerName = getRandomShopOwnerIGN();
            int shopItemId = hiredMerchantsList.get(random.nextInt(hiredMerchantsList.size()));
            Client cm = Client.createMock();
            cm.setWorld(channel.getWorld());
            cm.setChannel(channel.getId());
            Character newchar = Character.getDefault(cm);
            newchar.setID(ownerId);
            newchar.setName(ownerName);
            cm.setPlayer(newchar);
            newchar.setPosition(grounded);
            newchar.setMap(map);

            generateHiredMerchantShopData(newchar, ownerName, ownerId, "", shopItemId, mapId);
            ensureShopHasItems(newchar.getHiredMerchant());
            HiredMerchant spawned = newchar.getHiredMerchant();
            addMerchantToChannel(newchar, channel);
            MarketBotLog.info("shop ok map={} ch={} owner={} item={} pos={},{} oid={}",
                    mapId, channel.getId(), ownerName, shopItemId, grounded.x, grounded.y,
                    spawned == null ? -1 : spawned.getObjectId());
            return true;
        } catch (Exception e) {
            releaseMarketShopSlot(channel.getId(), mapId);
            MarketBotLog.error("hired merchant spawn failed map=" + mapId + " ch=" + channel.getId(), e);
            return false;
        }
    }

    private static void ensureShopHasItems(HiredMerchant merchant) {
        if (merchant == null || !merchant.getItems().isEmpty()) {
            return;
        }
        Item potion = new Item(2000002, (short) 1, (short) 100);
        merchant.addItem(new PlayerShopItem(potion, (short) 20, 1));
        Item orange = new Item(2000001, (short) 1, (short) 100);
        merchant.addItem(new PlayerShopItem(orange, (short) 20, 1));
    }

    private static HiredMerchantArtificial generateHiredMerchantShopData(Character newchar, String ownerName, int ownerId, String description, int shop_item_id, int mapId) {
        HiredMerchantArtificial newMerch = createMerchantObject(newchar, ownerName, ownerId, description, shop_item_id);

        String tier = getTierForRoom(mapId);

        newMerch.setTier(tier);
        newMerch.setMapId(mapId);

        /* todo add all scrolls weps for class type shops */
        boolean hotRoom = isHotRoom(mapId);
        HiredMerchantArtificial.shopTypes primaryShopType = hotRoom
                ? selectHotRoomShopType()
                : selectShopTypeWeightedProbability();
        newMerch.setPrimary(primaryShopType);

        generatePrimaryShop(primaryShopType, newMerch);

        if (hotRoom) {
            generateBonusEquipsForHotRoom(newMerch);
            generateSecondaryShopItems(newMerch);
            generateSecondaryShopItems(newMerch);
            fillHotRoomToMinimum(newMerch);
        } else {
            generateSecondaryShopItems(newMerch);
            generateTertiaryBackupShop(newMerch);
        }

        new FMShopDescriptionManager().generateDescription(newMerch);

        // special rules shop modifications
        applyAdditionalShopMods(newMerch);
        buyoutSomeItems(newMerch);
        applySpecialShopType(newMerch);

        appendRoomNumber(newMerch);
        ensureShopHasItems(newMerch);
        return newMerch;
    }

    private static void generatePrimaryShop(HiredMerchantArtificial.shopTypes choice, HiredMerchantArtificial merchant) {
        /*
        1. Class Oriented
            Common
            Warr
            Mage
            Bow
            Thief
                Stars
            Pirate
        2. Other Oriented
            Pot
            Scroll
            Dark Scroll
            Mastery
            Chair
            ETC

         Mix
            1. Class Oriented + 2. Other Oriented (Mini)
         */


        Runnable action = switch (choice) {
            case Warrior -> () -> {
                generateShop(merchant, Job.WARRIOR);
            };
            case Mage -> () -> {
                generateShop(merchant, Job.MAGICIAN);
            };
            case Bowman -> () -> {
                generateShop(merchant, Job.BOWMAN);
            };
            case Thief -> () -> {
                generateShop(merchant, Job.THIEF);
            };
            case Common -> () -> {
                generateShop(merchant, Job.BEGINNER);
            };
            case Pirate -> () -> {
                debugprint("Generating pirate shop");
                generateShop(merchant, Job.BEGINNER);
                // generatePirateEquipShop(merchant);
            };
            case Scroll -> () -> {
                repeatAction(3, () -> generateSecondaryShop(merchant, Scroll)); // generateScrollShop(newchar, tier));
            };
            case DarkScroll -> () -> {
                repeatAction(3, () -> generateSecondaryShop(merchant, DarkScroll)); // generateDarkScrollShop(newchar, tier));
            };
            case Potion -> () -> {
                repeatAction(3, () -> generateSecondaryShop(merchant, Potion)); // generateUseablesShop(newchar, tier));
            };
            case ETC -> () -> {
                repeatAction(3, () -> generateSecondaryShop(merchant, ETC)); // generateETCShop(newchar, tier));
            };
            case Chair -> () -> {
                repeatAction(5, () -> generateSecondaryShop(merchant, Chair)); // generateChairShop(newchar, tier));
            };
            case Mastery -> () -> {
                repeatAction(3, () -> generateSecondaryShop(merchant, Mastery)); // generateMasteryShop(newchar, tier));
            };
            default -> throw new IllegalArgumentException("Invalid shop type: " + choice);
        };
        action.run();
    }

    private static void generateSecondaryShopItems(HiredMerchantArtificial merchant) {
        // Randomly select 1 or 2 items based on weights
        List<HiredMerchantArtificial.shopTypes> selectedItems = getSecondaryShopItemTypes(); // getWeightedSelection(itemWeights);
        merchant.setSecondary(selectedItems.getFirst());

        for (HiredMerchantArtificial.shopTypes itemType : selectedItems) {
            applySecondaryShopItems(merchant, itemType);
        }
    }

    private static void applySecondaryShopItems(HiredMerchantArtificial merchant, HiredMerchantArtificial.shopTypes item) {
        switch (item) {
            case Potion:
                generateSecondaryShop(merchant, Potion);
                break;
            case Scroll:
                generateSecondaryShop(merchant, Scroll);
                break;
            case DarkScroll:
                generateSecondaryShop(merchant, DarkScroll);
                break;
            case Mastery:
                generateSecondaryShop(merchant, Mastery);
                break;
            case Chair:
                generateSecondaryShop(merchant, Chair);
                break;
            case ETC:
                generateSecondaryShop(merchant, ETC);
                break;
            default:
                debugprint("Unknown item: " + item);
        }
    }

    private static void generateTertiaryBackupShop(HiredMerchantArtificial merchant) {
        if (merchant.getItems().size() < 5) {
            int choice = random.nextInt(5); // Random Equip Common thru Pirate
            HiredMerchantArtificial.shopTypes tertiary = HiredMerchantArtificial.shopTypes.values()[choice];
            merchant.setTertiary(tertiary);
            generatePrimaryShop(tertiary, merchant);
        }
    }

    private static final Job[] CLASS_JOBS = {Job.WARRIOR, Job.MAGICIAN, Job.BOWMAN, Job.THIEF, Job.BEGINNER};

    private static void generateBonusEquipsForHotRoom(HiredMerchantArtificial merchant) {
        Job bonusClass = CLASS_JOBS[random.nextInt(CLASS_JOBS.length)];
        generateShop(merchant, bonusClass);
    }

    private static void fillHotRoomToMinimum(HiredMerchantArtificial merchant) {
        int attempts = 0;
        while (merchant.getItems().size() < 10 && attempts < 3) {
            Job fillClass = CLASS_JOBS[random.nextInt(CLASS_JOBS.length)];
            generateShop(merchant, fillClass);
            attempts++;
        }
    }

    private static HiredMerchantArtificial createMerchantObject(Character newchar, String ownerName, int ownerId, String description, int shopItemId) {
        HiredMerchantArtificial merchant = new HiredMerchantArtificial(newchar, description, shopItemId, ownerId, ownerName);
        newchar.setHiredMerchant(merchant);
        World world = Server.getInstance().getWorld(newchar.getClient().getWorld());
        world.registerHiredMerchant(merchant);
        world.getChannel(newchar.getClient().getChannel()).addHiredMerchant(ownerId, merchant);
        return merchant;
    }

    private static HiredMerchant addMerchantToChannel(Character newchar, Channel channel) {
        HiredMerchant merchant = newchar.getHiredMerchant();
        newchar.setHasMerchant(true);
        merchant.setOpen(true);
        merchant.getMap().addMapObject(merchant);
        newchar.setHiredMerchant(null);
        merchant.getMap().broadcastMessage(PacketCreator.spawnHiredMerchantBox(merchant));
        return merchant;
    }

    private static double getHiredMerchantChance(int mapId) {
        return switch (mapId) {
            case 910000001 -> 0.90;
            case 910000002 -> 0.80;
            case 910000007 -> 0.70;
            case 910000003 -> 0.60;
            default -> 0.40;
        };
    }

    private static boolean calculateSkippedSpot(int mapId) {
        if (mapId >= 910000000 && mapId <= 910000012) {
            return false;
        }
        Map<String, Double> regionProbabilities = Map.of(
                "henesys", 0.002,
                "ludi", 0.04,
                "perion", 0.10,
                "elnath", 0.15
        );
        for (Map.Entry<String, Double> entry : regionProbabilities.entrySet()) {
            if (fmInfo.getRegionFMMapId(entry.getKey()).contains(mapId)) {
                return Math.random() < entry.getValue();
            }
        }
        return false;
    }

    private static void applySpecialShopType(HiredMerchantArtificial merchant) {
        Random random = new Random();
        int roll = random.nextInt(10_000);
        if (roll == 0) { // 1 in 10,000 chance
            setOneMesoShop(merchant);
            setMerchantDescription(merchant, "一金币店");
            return;
        }
        if (roll < 100) { // 100 in 10,000 chance (1%)
            // Quitting Sale
            applyQuittingSaleDiscount(merchant);
            appendMerchantDescription(merchant, "清仓");
            return;
        }
        if (roll < 800) { // 800 in 10,000 chance (7%)
            applyCheapSaleDiscount(merchant);
            appendMerchantDescription(merchant, "低价");
            return;
        }
    }

    // doesnt work
    public static void destroyAllShops(Client c) {
        debugprint("Destroy all shops");
        c.getWorldServer().getChannel(1).closeAllMerchants();
//        c.getChannelServer().closeAllMerchants();
    }

    private static void repeatAction(int times, Runnable action) {
        for (int i = 0; i < times; i++) {
            action.run();
        }
    }

    /////////////////////////////////

    // Bot Store Permits

    public static void BotPlayerStorePermit(Character fakechar) {
        String desc = "小店";
        Integer shopItemId = getRandomStorePermitId();
        PlayerShop ps = new PlayerShop(fakechar, desc, shopItemId);
        fakechar.setPlayerShop(ps);
        fakechar.getMap().addMapObject(ps);

        HiredMerchantArtificial hma = generateHiredMerchantShopData(fakechar, fakechar.getName(), fakechar.getId(), desc, 5030000, fakechar.getMapId());
        String desc2 = hma.getDescription();
        ps.setDescription(desc2);
        List<PlayerShopItem> premadeShop = hma.getItems();
        ps.setItems(premadeShop);

        // open shop on map
        PlayerShop fakecharplayershop = fakechar.getPlayerShop();
        fakecharplayershop.setOpen(true);


    }

//    public static void testchoice() {
//        // Create a map to store the counts of each choice
//        Map<Integer, Integer> choiceCounts = new HashMap<>();
//
//        // Initialize counts for each choice to 0
//        for (int key : shopTypeWeights.keySet()) {
//            choiceCounts.put(key, 0);
//        }
//
//        // Run the selection process 1000 times
//        for (int i = 0; i < 1000; i++) {
//            int choice = selectShopTypeWeightedProbability();
//            choiceCounts.put(choice, choiceCounts.getOrDefault(choice, 0) + 1);
//        }
//
//        // Print the results
//        debugprint("Results after 1000 runs:");
//        for (Map.Entry<Integer, Integer> entry : choiceCounts.entrySet()) {
//            debugprint("Choice " + entry.getKey() + ": " + entry.getValue() + " times");
//        }
//    }

    public static void main(String[] args) {
//        testchoice();
    }

////    private static final int THREAD_POOL_SIZE = Math.min(Runtime.getRuntime().availableProcessors() * 8, 30);
////    private static final ExecutorService executor = Executors.newFixedThreadPool(THREAD_POOL_SIZE);
//    private static final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);

    public static void createBotShopAtLocation(Point position, int mapId) {
        if (mapId == 910000000) {
            MarketBotLog.info("skip bot shop at FM entrance");
            return;
        }
        if (!SoloMaplingConfig.fmRegionFillEnabled()) {
            debugprint("Free Market bot shop disabled by config: " + mapId);
            return;
        }
        int channelId = BotClientHandler.ensureStandaloneClient().getChannel();
        if (!reserveMarketShopSlot(channelId, mapId)) {
            return;
        }
        getExecutorService().submit(() -> {
            debugprint("Making shop at: " + mapId + ", " + position);
            Character fakechar2 = createBotPollReadiness(position, mapId, true);
            if (fakechar2 == null) {
                System.err.println("Bot not ready after 3 seconds, skipping store");
                releaseMarketShopSlot(channelId, mapId);
                return;
            }
            getScheduledExecutorService().schedule(() -> runAsync(() -> {
                BotPlayerStorePermit(fakechar2);

                if (Math.random() < 0.5) {
                    microTurnAround(fakechar2);
                }
                if (Math.random() < 0.4) {
                    getScheduledExecutorService().schedule(() -> botSitChair(fakechar2, getRandomChairId()),
                            500, TimeUnit.MILLISECONDS);
                }
            }), 1200, TimeUnit.MILLISECONDS);
        });
    }

    private static boolean reserveMarketShopSlot(int channelId, int mapId) {
        AtomicInteger perMap = shopsByMap.computeIfAbsent(channelId + ":" + mapId, ignored -> new AtomicInteger());
        int cap = Math.max(SoloMaplingConfig.marketShopMax(), 24);
        while (true) {
            int current = perMap.get();
            if (current >= cap) {
                debugprint("Free Market shop limit reached for map " + mapId + ": " + cap);
                return false;
            }
            if (perMap.compareAndSet(current, current + 1)) {
                marketShopCount.incrementAndGet();
                return true;
            }
        }
    }

    private static void releaseMarketShopSlot(int channelId, int mapId) {
        AtomicInteger perMap = shopsByMap.get(channelId + ":" + mapId);
        if (perMap != null) {
            perMap.updateAndGet(value -> Math.max(0, value - 1));
        }
        marketShopCount.updateAndGet(value -> Math.max(0, value - 1));
    }
}
