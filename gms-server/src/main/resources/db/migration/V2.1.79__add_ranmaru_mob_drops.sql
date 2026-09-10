-- Momijigaoka field mobs and Mori Ranmaru boss meso/potion drops.
CREATE TEMPORARY TABLE `ranmaru_field_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);
INSERT INTO `ranmaru_field_mob_ids` (`mobid`) VALUES
(9421511),
(9421512),
(9421513),
(9421514);

CREATE TEMPORARY TABLE `ranmaru_boss_mob_ids` (
    `mobid` INT NOT NULL PRIMARY KEY
);
INSERT INTO `ranmaru_boss_mob_ids` (`mobid`) VALUES
(9421581),
(9421583);

INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 400, 800, 0, 400000 FROM `ranmaru_field_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 1, 0, 100000 FROM `ranmaru_field_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 0, 8000, 16000, 0, 400000 FROM `ranmaru_boss_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
SELECT `mobid`, 2000005, 1, 3, 0, 200000 FROM `ranmaru_boss_mob_ids`
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
