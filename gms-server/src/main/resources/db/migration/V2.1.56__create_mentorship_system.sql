CREATE TABLE IF NOT EXISTS `mentorship_relation`
(
    `id`                       INT(11)      NOT NULL AUTO_INCREMENT,
    `master_cid`               INT(11)      NOT NULL,
    `master_accountid`         INT(11)      NOT NULL,
    `master_name`              VARCHAR(13)  NOT NULL,
    `apprentice_cid`           INT(11)      NOT NULL,
    `apprentice_accountid`     INT(11)      NOT NULL,
    `apprentice_name`          VARCHAR(13)  NOT NULL,
    `guildid`                  INT(10)      NOT NULL,
    `status`                   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '0 active, 1 graduated, 2 cancelled',
    `start_time`               TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `graduate_time`            TIMESTAMP    NULL     DEFAULT NULL,
    `start_master_power`       BIGINT       NOT NULL DEFAULT 0,
    `start_apprentice_power`   BIGINT       NOT NULL DEFAULT 0,
    `last_master_power`        BIGINT       NOT NULL DEFAULT 0,
    `last_apprentice_power`    BIGINT       NOT NULL DEFAULT 0,
    `reward_step`              INT(11)      NOT NULL DEFAULT 0,
    `total_points`             INT(11)      NOT NULL DEFAULT 0,
    `update_time`              TIMESTAMP    NULL     ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_mentorship_master_status` (`master_cid`, `status`),
    KEY `idx_mentorship_apprentice_status` (`apprentice_cid`, `status`),
    KEY `idx_mentorship_guild_status` (`guildid`, `status`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS `mentorship_wallet`
(
    `characterid`     INT(11)   NOT NULL,
    `apprentice_coin` INT(11)   NOT NULL DEFAULT 0 COMMENT '师徒币',
    `virtue_coin`     INT(11)   NOT NULL DEFAULT 0 COMMENT '师德币',
    `total_points`    INT(11)   NOT NULL DEFAULT 0,
    `weekly_points`   INT(11)   NOT NULL DEFAULT 0,
    `update_time`     TIMESTAMP NULL     ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`characterid`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS `mentorship_weekly_pool`
(
    `relationid` INT(11)     NOT NULL,
    `week_key`   VARCHAR(8)  NOT NULL,
    `points`     INT(11)     NOT NULL DEFAULT 0,
    `claim_master` INT(11)   NOT NULL DEFAULT 0,
    `claim_apprentice` INT(11) NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP   NULL     ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`relationid`, `week_key`),
    KEY `idx_mentorship_week_points` (`week_key`, `points`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS `mentorship_duel`
(
    `id`             INT(11)    NOT NULL AUTO_INCREMENT,
    `relation_a`     INT(11)    NOT NULL,
    `relation_b`     INT(11)    NULL     DEFAULT NULL,
    `stake`          INT(11)    NOT NULL DEFAULT 0,
    `points_a`       INT(11)    NOT NULL DEFAULT 0,
    `points_b`       INT(11)    NOT NULL DEFAULT 0,
    `status`         TINYINT(1) NOT NULL DEFAULT 0 COMMENT '0 queued, 1 active, 2 finished, 3 cancelled',
    `winner_relation` INT(11)   NULL     DEFAULT NULL,
    `created_at`     TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `started_at`     TIMESTAMP  NULL     DEFAULT NULL,
    `ends_at`        TIMESTAMP  NULL     DEFAULT NULL,
    `finished_at`    TIMESTAMP  NULL     DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_mentorship_duel_status` (`status`, `ends_at`),
    KEY `idx_mentorship_duel_relation_a` (`relation_a`, `status`),
    KEY `idx_mentorship_duel_relation_b` (`relation_b`, `status`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS `mentorship_event_log`
(
    `event_key`  VARCHAR(96) NOT NULL,
    `relationid` INT(11)     NOT NULL,
    `points`     INT(11)     NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`event_key`, `relationid`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

INSERT INTO `plife` (`world`, `map`, `life`, `type`, `cy`, `f`, `fh`, `rx0`, `rx1`, `x`, `y`, `hide`, `mobtime`, `team`)
SELECT 0, 910000000, 3003107, 'n', 88, 0, 1, -220, -120, -170, 88, 0, 0, 0
WHERE NOT EXISTS (
    SELECT 1 FROM `plife`
    WHERE `world` = 0 AND `map` = 910000000 AND `life` = 3003107 AND `type` = 'n'
);
