-- Forgotten Valley quest and ETC drops from the map patch package.
-- Future Gate 860/861/885 quest drops are already covered by V2.1.20.
INSERT INTO `drop_data` (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(54, 4000900, 1, 1, 0, 600000),
(54, 4032900, 1, 1, 10600, 300000),
(55, 4000901, 1, 1, 0, 600000),
(56, 4000902, 1, 1, 0, 600000),
(57, 4000903, 1, 1, 0, 600000),
(58, 4000904, 1, 1, 0, 600000),
(59, 4000905, 1, 1, 0, 600000),
(60, 4000906, 1, 1, 0, 600000),
(61, 4000907, 1, 1, 0, 600000),
(62, 4000908, 1, 1, 0, 600000),
(63, 4000909, 1, 1, 0, 600000),
(63, 4032901, 1, 1, 10604, 300000),
(700003, 4000910, 1, 1, 0, 100000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
