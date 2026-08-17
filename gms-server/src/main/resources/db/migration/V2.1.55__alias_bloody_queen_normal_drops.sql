-- Normal Crimson Queen qualification boss used by the equipment evolution system.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8920101, 4260009, 1, 2, 0, 999999)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
