-- 神秘河 152 张地图实际使用的 83 种怪物掉落。
-- MSS206 的概率基数为 10000；换算到本项目 999999 基数时乘以 100。
-- 现代核心、箱子、药水和矿石在当前旧客户端均不存在，因此只映射到现存药水，
-- 并加入本次迁移的真实任务物品，避免服务端生成客户端无法识别的道具。
CREATE TEMPORARY TABLE `arcane_river_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);

INSERT INTO `arcane_river_mob_ids` (`mobid`) VALUES
(8641000), (8641001), (8641002), (8641003), (8641004), (8641005), (8641006), (8641007),
(8641013), (8641014), (8641015),
(8642000), (8642001), (8642002), (8642003), (8642004), (8642005), (8642006), (8642007),
(8642008), (8642009), (8642010), (8642011), (8642012), (8642013), (8642014), (8642015),
(8642017), (8642018), (8642019), (8642020), (8642021), (8642022),
(8643000), (8643001), (8643002), (8643003), (8643004), (8643005), (8643006), (8643007),
(8643008), (8643009), (8643010), (8643011), (8643012), (8643014), (8643015), (8643016),
(8644000), (8644001), (8644002), (8644003), (8644004), (8644005), (8644006), (8644007),
(8644008), (8644009), (8644010),
(8644400), (8644401), (8644402), (8644403), (8644404), (8644405), (8644406), (8644407),
(8644408), (8644409), (8644410), (8644411), (8644412),
(8644500), (8644501), (8644502), (8644503), (8644504), (8644505), (8644506), (8644507),
(8644508), (8644509);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT
    `mobid`,
    0,
    CASE
        WHEN `mobid` < 8642000 THEN 1200
        WHEN `mobid` < 8643000 THEN 1400
        WHEN `mobid` < 8644000 THEN 1600
        ELSE 1800
    END,
    CASE
        WHEN `mobid` < 8642000 THEN 1800
        WHEN `mobid` < 8643000 THEN 2100
        WHEN `mobid` < 8644000 THEN 2400
        ELSE 2700
    END,
    0,
    400000
FROM `arcane_river_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 1, 0, 10000
FROM `arcane_river_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000006, 1, 1, 0, 10000
FROM `arcane_river_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);

DROP TEMPORARY TABLE `arcane_river_mob_ids`;

-- 任务物品仅在对应任务进行中掉落，50% 为 MSS206 的 5000/10000 对齐值。
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8641000, 4034914, 1, 1, 34102, 500000),
(8641001, 4034915, 1, 1, 34103, 500000),
(8641002, 4034916, 1, 1, 34104, 500000),
(8641003, 4034917, 1, 1, 34105, 500000),
(8642000, 4034942, 1, 1, 34203, 500000),
(8643001, 4034979, 1, 1, 34303, 500000),
(8643005, 4034981, 1, 1, 34314, 500000),
(8643006, 4034982, 1, 1, 34315, 500000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
