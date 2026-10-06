CREATE TABLE `wallet_auth_sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_wallet_session_expiry` ON `wallet_auth_sessions` (`expires_at`);