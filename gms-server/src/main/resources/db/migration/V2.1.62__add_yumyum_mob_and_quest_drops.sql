-- 真香岛 12 种地图怪物的基础掉落，以及啾啾/真香任务物品掉落。
-- 旧端任务封包按 signed short 读取，因此 questid 使用对应负数。
CREATE TEMPORARY TABLE `yumyum_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);

INSERT INTO `yumyum_mob_ids` (`mobid`) VALUES
(8642050), (8642051), (8642052), (8642053), (8642054), (8642055),
(8642060), (8642061), (8642062), (8642063), (8642064), (8642065);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 1400, 2100, 0, 400000
FROM `yumyum_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 1, 0, 100000
FROM `yumyum_mob_ids`
ON DUPLICATE KEY UPDATE `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000006, 1, 1, 0, 100000
FROM `yumyum_mob_ids`
ON DUPLICATE KEY UPDATE `chance` = VALUES(`chance`);

DROP TEMPORARY TABLE `yumyum_mob_ids`;

-- 啾啾主线食材：对应地图怪物与 signed-16 任务号。
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8642000, 4034942, 1, 1, -31333, 500000),
(8642001, 4034943, 1, 1, -31329, 500000),
(8642002, 4034944, 1, 1, -31328, 500000),
(8642003, 4034945, 1, 1, -31328, 500000),
(8642004, 4034946, 1, 1, -31327, 500000),
(8642005, 4034947, 1, 1, -31327, 500000),
(8642006, 4034948, 1, 1, -31326, 500000),
(8642007, 4034949, 1, 1, -31326, 500000),
(8642008, 4034950, 1, 1, -31325, 500000),
(8642009, 4034951, 1, 1, -31325, 500000),
(8642010, 4034952, 1, 1, -31324, 500000),
(8642011, 4034953, 1, 1, -31324, 500000),
(8642012, 4034954, 1, 1, -31323, 500000),
(8642013, 4034955, 1, 1, -31323, 500000),
(8642014, 4034956, 1, 1, -31322, 500000),
(8642015, 4034957, 1, 1, -31322, 500000),
(8642015, 4034958, 1, 1, -31321, 500000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

-- 每日收集任务物品由区域内所有对应怪物掉落。
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 4036571, 1, 1, -26503, 250000
FROM (
    SELECT 8642000 AS `mobid` UNION ALL SELECT 8642001 UNION ALL SELECT 8642002
    UNION ALL SELECT 8642003 UNION ALL SELECT 8642004 UNION ALL SELECT 8642005
    UNION ALL SELECT 8642006 UNION ALL SELECT 8642007 UNION ALL SELECT 8642008
    UNION ALL SELECT 8642009 UNION ALL SELECT 8642010 UNION ALL SELECT 8642011
    UNION ALL SELECT 8642012 UNION ALL SELECT 8642013 UNION ALL SELECT 8642014
    UNION ALL SELECT 8642015
) AS `chewchew_mobs`
ON DUPLICATE KEY UPDATE `questid` = VALUES(`questid`), `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 4036710, 1, 1, -26466, 250000
FROM (
    SELECT 8642050 AS `mobid` UNION ALL SELECT 8642051 UNION ALL SELECT 8642052
    UNION ALL SELECT 8642053 UNION ALL SELECT 8642054 UNION ALL SELECT 8642055
    UNION ALL SELECT 8642060 UNION ALL SELECT 8642061 UNION ALL SELECT 8642062
    UNION ALL SELECT 8642063 UNION ALL SELECT 8642064 UNION ALL SELECT 8642065
) AS `yumyum_quest_mobs`
ON DUPLICATE KEY UPDATE `questid` = VALUES(`questid`), `chance` = VALUES(`chance`);
