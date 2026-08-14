DELETE FROM `cooldowns`
WHERE `SkillID` = 4121012;

DELETE FROM `keymap`
WHERE `action` = 4121012;

DELETE FROM `skillmacros`
WHERE `skill1` = 4121012
   OR `skill2` = 4121012
   OR `skill3` = 4121012;

DELETE FROM `skills`
WHERE `skillid` = 4121012;
