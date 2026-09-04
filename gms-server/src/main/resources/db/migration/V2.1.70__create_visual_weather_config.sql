CREATE TABLE IF NOT EXISTS `weather_config` (
    `id` TINYINT NOT NULL,
    `enabled` TINYINT(1) NOT NULL DEFAULT 1,
    `day_length_ms` BIGINT NOT NULL DEFAULT 14400000,
    `change_interval_ms` BIGINT NOT NULL DEFAULT 900000,
    `override_hold_ms` BIGINT NOT NULL DEFAULT 3600000,
    `rainbow_duration_sec` INT NOT NULL DEFAULT 180,
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `weather_config`
    (`id`, `enabled`, `day_length_ms`, `change_interval_ms`, `override_hold_ms`, `rainbow_duration_sec`)
SELECT 1, 1, 14400000, 900000, 3600000, 180
WHERE NOT EXISTS (SELECT 1 FROM `weather_config` WHERE `id` = 1);

CREATE TABLE IF NOT EXISTS `weather_region_config` (
    `region` VARCHAR(32) NOT NULL,
    `forced_profile` VARCHAR(16) NULL,
    `clear_weight` DECIMAL(8,3) NOT NULL,
    `rain_weight` DECIMAL(8,3) NOT NULL,
    `snow_weight` DECIMAL(8,3) NOT NULL,
    `overcast_weight` DECIMAL(8,3) NOT NULL,
    `storm_weight` DECIMAL(8,3) NOT NULL,
    `blizzard_weight` DECIMAL(8,3) NOT NULL,
    `leaves_weight` DECIMAL(8,3) NOT NULL,
    `blossom_weight` DECIMAL(8,3) NOT NULL,
    `sandstorm_weight` DECIMAL(8,3) NOT NULL,
    `night_tint` INT NOT NULL,
    `palette_id` TINYINT UNSIGNED NOT NULL,
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`region`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
