-- Lion King's Castle quest-limited field drops.
-- drop_data chance scale: 1,000,000 = 100%.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
VALUES
    (8840002, 4032831, 1, 1, 3164, 800000),
    (8210005, 4032835, 1, 1, 3170, 400000),
    (8210004, 4032836, 1, 1, 3174, 400000),
    (8210000, 4032838, 1, 1, 3177, 400000),
    (8210001, 4032838, 1, 1, 3177, 400000),
    (8210002, 4032838, 1, 1, 3177, 400000),
    (8210003, 4032838, 1, 1, 3177, 400000),
    (8210004, 4032838, 1, 1, 3177, 400000),
    (8210013, 4032839, 1, 1, 3178, 800000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
