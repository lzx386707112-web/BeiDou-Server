package soloMapling.FreeMarket;

import org.junit.jupiter.api.Test;
import soloMapling.ArtificialPlayer.BotTypes.FMBot;
import soloMapling.Environment.EnvironmentManager;
import soloMapling.Environment.PlatformParser;
import soloMapling.Environment.PlatformSpawner;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MarketBotBehaviorTest {
    @Test
    void sellingLineIncludesItemName() {
        String line = MarketBotFlavor.selling("祝福卷轴");
        assertTrue(line.contains("祝福卷轴"));
        assertTrue(line.contains("出") || line.contains("甩") || line.contains("处理"));
    }

    @Test
    void buyingLineIncludesItemAndPrice() {
        String line = MarketBotFlavor.buying("祝福卷轴", "50万");
        assertTrue(line.contains("祝福卷轴"));
        assertTrue(line.contains("50万"));
    }

    @Test
    void shouldNotBuyClearlyOverpricedItems() {
        assertFalse(FMBot.shouldPurchaseItem(150, 100));
        assertFalse(FMBot.shouldPurchaseItem(0, 100));
        assertFalse(FMBot.shouldPurchaseItem(50, null));
    }

    @Test
    void entranceWanderersScaleWithCapWithoutExceedingTwoThirds() {
        assertArrayEquals(new int[]{0, 0, 0}, EnvironmentManager.distributeMarketEntranceWanderers(0));
        int[] atTen = EnvironmentManager.distributeMarketEntranceWanderers(10);
        assertArrayEquals(new int[]{2, 2, 2}, atTen);
        int[] atThirty = EnvironmentManager.distributeMarketEntranceWanderers(30);
        assertArrayEquals(new int[]{6, 6, 8}, atThirty);
        assertTrue(atThirty[0] + atThirty[1] + atThirty[2] <= 20);
    }

    @Test
    void fmEntrancePlatformsHaveWalkableWidth() {
        var m1 = PlatformParser.parsePlatform(910000000, "m1");
        var m2 = PlatformParser.parsePlatform(910000000, "m2");
        var m5 = PlatformParser.parsePlatform(910000000, "m5");
        assertTrue(m1.getWidth() > 200);
        assertTrue(m2.getWidth() > 200);
        assertTrue(m5.getWidth() > 200);
        assertTrue(PlatformParser.listPlatformIds(910000000).containsAll(List.of("m1", "m2", "m5")));
    }

    @Test
    void snapToGroundWithoutMapKeepsPoint() {
        var raw = new java.awt.Point(100, 4);
        var snapped = PlatformSpawner.snapToGround(null, raw);
        assertEquals(100, snapped.x);
        assertEquals(4, snapped.y);
    }

    @Test
    void patrolTargetStaysOnPlatformAndWalksALongWay() {
        var platform = PlatformParser.parsePlatform(910000000, "m1");
        var rng = java.util.concurrent.ThreadLocalRandom.current();
        var left = MarketBotAmbient.patrolTarget(platform, platform.getMinX() + 40, rng);
        var right = MarketBotAmbient.patrolTarget(platform, platform.getMaxX() - 40, rng);
        assertTrue(left.x >= platform.getMinX() && left.x <= platform.getMaxX());
        assertTrue(right.x >= platform.getMinX() && right.x <= platform.getMaxX());
        assertTrue(Math.abs(left.x - (platform.getMinX() + 40)) >= 120);
        assertTrue(Math.abs(left.x - (platform.getMinX() + 40)) <= 281);
        assertTrue(Math.abs(right.x - (platform.getMaxX() - 40)) >= 120);
        assertTrue(Math.abs(right.x - (platform.getMaxX() - 40)) <= 281);
    }

    @Test
    void hiredMerchantRoomsDoNotIncludeEntrance() {
        assertFalse(FMShopInfoManager.henesysRegionFM.contains(910000000));
        assertFalse(FMShopInfoManager.ludiRegionFM.contains(910000000));
        assertTrue(FMShopInfoManager.henesysRegionFM.contains(910000001));
        assertTrue(FMShopInfoManager.ludiRegionFM.contains(910000007));
    }

    @Test
    void marketRoomsUseMatchingRegionShopCoordinates() {
        assertEquals("henesys", FMShopInfoManager.getRegionByMapId(910000001));
        assertEquals("ludi", FMShopInfoManager.getRegionByMapId(910000007));
        var henesys = new FMShopInfoManager().getRegionFMSpots("henesys");
        var ludi = new FMShopInfoManager().getRegionFMSpots("ludi");
        assertTrue(henesys.stream().allMatch(p -> p.x > -400 && p.x < 900));
        assertTrue(ludi.stream().allMatch(p -> p.x < -100));
        assertFalse(FMShopInfoManager.hiredMerchantItemIds.contains(5030010));
        assertTrue(FMShopInfoManager.hiredMerchantItemIds.contains(5030000));
    }

    @Test
    void itemSelectorLoadsYamlFromSourceTree() {
        var item = soloMapling.itemPool.ItemSelector.getRandomItemFull("useables.yaml", "Potions", "S");
        assertTrue(item == null || item.getVariantId() != null);
    }

    @Test
    void shopOwnerNameNeverThrowsWhenNameFileMissingFromCwd() {
        String name = FMShopDescGen.getRandomShopOwnerIGN();
        assertFalse(name == null || name.isBlank());
        assertTrue(name.length() <= 13);
        assertFalse(MarketShopTitles.hasLatin(name));
    }

    @Test
    void shopTitlesAreChinese() {
        for (String type : List.of("common", "thief", "warrior", "mage", "bowman", "chair", "scrolls", "useable", "etc", "fmclan", "shortword", "emojis")) {
            for (int i = 0; i < 20; i++) {
                String title = FMShopDescGen.getRandomStoreDescription(type);
                assertFalse(title == null || title.isBlank(), type);
                assertFalse(MarketShopTitles.hasLatin(title), type + " -> " + title);
            }
        }
        assertFalse(MarketShopTitles.hasLatin(MarketShopTitles.welcome("小枫")));
        assertFalse(MarketShopTitles.hasLatin(MarketShopTitles.randomOffer()));
        assertFalse(MarketShopTitles.hasLatin(MarketShopTitles.randomCurrency()));
    }

    @Test
    void mountPairsComeFromTrendFrontScript() {
        assertEquals(1902000, MarketBotAmbient.MOUNT_PAIRS[0][0]);
        assertEquals(1912000, MarketBotAmbient.MOUNT_PAIRS[0][1]);
        assertTrue(MarketBotAmbient.MOUNT_PAIRS.length >= 3);
    }

    @Test
    void chatBankHasManyChineseLines() {
        assertTrue(MarketBotFlavor.lineCount() > 400);
        for (int i = 0; i < 40; i++) {
            String line = MarketBotFlavor.chat();
            assertFalse(line.isBlank());
            assertTrue(line.codePoints().anyMatch(cp -> java.lang.Character.UnicodeScript.of(cp) == java.lang.Character.UnicodeScript.HAN)
                    || line.contains("？") || line.contains("。"));
        }
        String a = MarketBotFlavor.wander();
        String b = MarketBotFlavor.wander();
        String c = MarketBotFlavor.wander();
        assertFalse(a.equals(b) && b.equals(c));
    }
}
