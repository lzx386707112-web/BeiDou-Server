-- Special materials required by the reworked ten-stage equipment evolution chain.
INSERT INTO `drop_data`
    (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(3220000, 4031543, 1, 1, 0, 50000),
(2220000, 4031543, 1, 1, 0, 50000),
(5220002, 4031544, 1, 1, 0, 50000),
(5220000, 4031545, 1, 1, 0, 50000),
(4130103, 1002006, 1, 1, 0, 30000),
(7220001, 1002761, 1, 1, 0, 30000),
(8130100, 1004556, 1, 1, 0, 30000),
(8220001, 1702598, 1, 1, 0, 30000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
