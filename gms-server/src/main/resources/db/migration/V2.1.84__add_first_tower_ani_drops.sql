-- First tower roof now spawns 8210010 instead of the Von Leon clone 8840002.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`)
VALUES
    (8210010, 0, 500, 900, 0, 400000),
    (8210010, 2000005, 1, 1, 0, 100000),
    (8210010, 4032831, 1, 1, 3164, 800000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
