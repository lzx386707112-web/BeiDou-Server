-- Quest-limited collection drops for the installed Odium and Shangri-La quests.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8645291, 4036894, 1, 1, -27220, 500000),
(8645294, 4036895, 1, 1, -27217, 500000),
(8645297, 4036896, 1, 1, -27214, 500000),
(8645372, 4037167, 1, 1, -27128, 500000),
(8645367, 4037168, 1, 1, -27127, 500000),
(8645368, 4037169, 1, 1, -27126, 500000),
(8645370, 4037170, 1, 1, -27125, 500000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
