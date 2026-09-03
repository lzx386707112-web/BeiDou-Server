CREATE TABLE IF NOT EXISTS `character_link`
(
    `target_cid` INT(11)   NOT NULL COMMENT 'receiving character',
    `source_cid` INT(11)   NOT NULL COMMENT 'earlier-created linked character',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`target_cid`, `source_cid`),
    KEY `idx_character_link_source` (`source_cid`),
    CONSTRAINT `fk_character_link_target`
        FOREIGN KEY (`target_cid`) REFERENCES `characters` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_character_link_source`
        FOREIGN KEY (`source_cid`) REFERENCES `characters` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;
