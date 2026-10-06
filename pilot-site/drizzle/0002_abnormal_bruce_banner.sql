CREATE TABLE `wallet_auth_challenges` (
	`nonce` text PRIMARY KEY NOT NULL,
	`browser` text NOT NULL,
	`address` text NOT NULL,
	`origin` text NOT NULL,
	`message` text NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_wallet_challenge_expiry` ON `wallet_auth_challenges` (`expires_at`);--> statement-breakpoint
CREATE INDEX `idx_wallet_challenge_browser` ON `wallet_auth_challenges` (`browser`);--> statement-breakpoint
CREATE TABLE `wallet_auth_limits` (
	`bucket` text PRIMARY KEY NOT NULL,
	`count` integer NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_wallet_limit_expiry` ON `wallet_auth_limits` (`expires_at`);