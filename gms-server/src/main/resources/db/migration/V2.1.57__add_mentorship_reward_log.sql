CREATE TABLE IF NOT EXISTS `mentorship_reward_log`
(
    `relationid` INT(11)     NOT NULL,
    `reward_key` VARCHAR(64) NOT NULL,
    `created_at` TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`relationid`, `reward_key`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;
