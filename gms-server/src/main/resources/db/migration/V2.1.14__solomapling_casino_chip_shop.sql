INSERT INTO `shops` (`shopid`, `npcid`)
VALUES (9999001, 9000055)
ON DUPLICATE KEY UPDATE `npcid` = VALUES(`npcid`);

INSERT INTO `shopitems` (`shopid`, `itemid`, `price`, `pitch`, `position`)
VALUES
    (9999001, 4002000, 10000, 0, 4),
    (9999001, 4002001, 50000, 0, 3),
    (9999001, 4002002, 250000, 0, 2),
    (9999001, 4002003, 1000000, 0, 1)
ON DUPLICATE KEY UPDATE
    `price` = VALUES(`price`),
    `pitch` = VALUES(`pitch`),
    `position` = VALUES(`position`);
