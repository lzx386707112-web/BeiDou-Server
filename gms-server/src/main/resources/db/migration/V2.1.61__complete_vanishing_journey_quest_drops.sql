-- The legacy client stores modern quest IDs as signed 16-bit values.
-- 34102-34118 therefore become -31434 through -31418 on the wire and in WZ.
-- Re-upsert the original four rows so already-migrated databases are corrected.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8641000, 4034914, 1, 1, -31434, 500000),
(8641001, 4034915, 1, 1, -31433, 500000),
(8641002, 4034916, 1, 1, -31432, 500000),
(8641003, 4034917, 1, 1, -31431, 500000),
(8641004, 4034918, 1, 1, -31425, 500000),
(8641005, 4034919, 1, 1, -31424, 500000),
(8641006, 4034920, 1, 1, -31423, 500000),
(8641007, 4034921, 1, 1, -31420, 500000),
(8641007, 4034937, 1, 1, -31419, 500000),
(8641007, 4034938, 1, 1, -31418, 500000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
