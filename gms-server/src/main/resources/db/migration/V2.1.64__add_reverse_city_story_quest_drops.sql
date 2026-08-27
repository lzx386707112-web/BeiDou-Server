-- Reverse City story collection drops from TMS quests 37604, 37606,
-- 37610, 37612 and 37615. Chance uses the existing Arcane River rate.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8641051, 4036631, 1, 1, -27932, 500000),
(8641052, 4036632, 1, 1, -27930, 500000),
(8641054, 4036633, 1, 1, -27926, 500000),
(8641055, 4036634, 1, 1, -27924, 500000),
(8641055, 4036635, 1, 1, -27921, 500000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
