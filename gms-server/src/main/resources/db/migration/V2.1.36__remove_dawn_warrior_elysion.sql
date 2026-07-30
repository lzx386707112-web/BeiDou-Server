DELETE FROM `cooldowns`
WHERE `SkillID` = 11121010;

DELETE FROM `keymap`
WHERE `action` = 11121010;

DELETE FROM `skillmacros`
WHERE `skill1` = 11121010
   OR `skill2` = 11121010
   OR `skill3` = 11121010;

DELETE FROM `skills`
WHERE `skillid` = 11121010;
