ALTER TABLE `wallet_auth_sessions` ADD `browser` text DEFAULT '' NOT NULL;--> statement-breakpoint
CREATE INDEX `idx_wallet_session_browser` ON `wallet_auth_sessions` (`browser`);