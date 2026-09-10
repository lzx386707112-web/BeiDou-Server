-- Later tower roofs now spawn 8210011/8210012/8210014 instead of
-- boss-flagged instructors 8210006/8210007 or an empty fourth roof.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
VALUES
    (8210011, 0, 520, 940, 0, 400000),
    (8210011, 2000005, 1, 1, 0, 100000),
    (8210012, 0, 560, 1000, 0, 400000),
    (8210012, 2000005, 1, 1, 0, 100000),
    (8210014, 0, 600, 1100, 0, 400000),
    (8210014, 2000005, 1, 1, 0, 100000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
