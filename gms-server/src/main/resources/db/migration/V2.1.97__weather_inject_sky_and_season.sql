ALTER TABLE `weather_config`
    ADD COLUMN `inject_sky` TINYINT(1) NOT NULL DEFAULT 1 AFTER `rainbow_duration_sec`,
    ADD COLUMN `season_drift` TINYINT(1) NOT NULL DEFAULT 1 AFTER `inject_sky`;
