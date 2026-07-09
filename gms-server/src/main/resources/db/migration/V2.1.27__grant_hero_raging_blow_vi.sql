INSERT INTO skills (characterid, skillid, skilllevel, masterlevel, expiration)
SELECT id, 1121013, 30, 30, -1
FROM characters
WHERE job = 112
ON DUPLICATE KEY UPDATE
    skilllevel = 30,
    masterlevel = 30,
    expiration = -1;
