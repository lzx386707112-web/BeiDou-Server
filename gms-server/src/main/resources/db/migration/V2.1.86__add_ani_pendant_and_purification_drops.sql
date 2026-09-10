-- 3178 pendant drop stays on 8210013; that mob now has a field spawn on 211061100.
-- 3199 purification totem and royal medals drop from installed castle field mobs.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
VALUES
    (8210000, 4000630, 1, 1, 3199, 400000),
    (8210001, 4000630, 1, 1, 3199, 400000),
    (8210002, 4000630, 1, 1, 3199, 400000),
    (8210003, 4000630, 1, 1, 3199, 400000),
    (8210004, 4000630, 1, 1, 3199, 400000),
    (8210005, 4000630, 1, 1, 3199, 400000),
    (8211000, 4000630, 1, 1, 3199, 400000),
    (8211001, 4000630, 1, 1, 3199, 400000),
    (8211002, 4000630, 1, 1, 3199, 400000),
    (8210000, 4310010, 1, 1, 3199, 80000),
    (8210001, 4310010, 1, 1, 3199, 80000),
    (8210002, 4310010, 1, 1, 3199, 80000),
    (8210003, 4310010, 1, 1, 3199, 80000),
    (8210004, 4310010, 1, 1, 3199, 120000),
    (8210005, 4310010, 1, 1, 3199, 150000),
    (8210013, 4310010, 1, 1, 3199, 200000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
