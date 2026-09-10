-- Mob 9500319 Happy White equipment: 0.7% each.
-- drop_data chance scale: 1,000,000 = 100%, so 0.7% = 7000.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
VALUES
    (9500319, 1322214, 1, 1, 0, 7000), -- 幸福白色铁瓜锤
    (9500319, 1332236, 1, 1, 0, 7000), -- 幸福白色切割者
    (9500319, 1382221, 1, 1, 0, 7000), -- 幸福白色长杖
    (9500319, 1402209, 1, 1, 0, 7000), -- 幸福白色双手剑
    (9500319, 1412145, 1, 1, 0, 7000), -- 幸福白色双手战斧
    (9500319, 1422150, 1, 1, 0, 7000), -- 幸福白色巨锤
    (9500319, 1432177, 1, 1, 0, 7000), -- 幸福白色之矛
    (9500319, 1462203, 1, 1, 0, 7000), -- 幸福白色之弩
    (9500319, 1472224, 1, 1, 0, 7000), -- 幸福白色拳甲
    (9500319, 1482178, 1, 1, 0, 7000), -- 幸福白色冲拳
    (9500319, 1492189, 1, 1, 0, 7000), -- 幸福白色手铳
    (9500319, 1003938, 1, 1, 0, 7000), -- 幸福白色帽子
    (9500319, 1102606, 1, 1, 0, 7000)  -- 幸福白色披风
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
