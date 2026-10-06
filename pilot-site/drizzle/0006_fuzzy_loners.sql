CREATE TABLE `local_auth_accounts` (
	`id` text PRIMARY KEY NOT NULL,
	`username` text NOT NULL,
	`salt` text NOT NULL,
	`password_hash` text NOT NULL,
	`kdf` text NOT NULL,
	`recovery_hash` text NOT NULL,
	`auth_version` text NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_local_account_username` ON `local_auth_accounts` (`username`);--> statement-breakpoint
CREATE TABLE `local_auth_challenges` (
	`nonce` text PRIMARY KEY NOT NULL,
	`csrf` text NOT NULL,
	`browser` text NOT NULL,
	`origin` text NOT NULL,
	`action` text NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_local_challenge_browser` ON `local_auth_challenges` (`browser`);--> statement-breakpoint
CREATE INDEX `idx_local_challenge_expiry` ON `local_auth_challenges` (`expires_at`);--> statement-breakpoint
CREATE TABLE `local_auth_sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`browser` text NOT NULL,
	`account_id` text NOT NULL,
	`auth_version` text NOT NULL,
	`origin` text NOT NULL,
	`expires_at` integer NOT NULL,
	FOREIGN KEY (`account_id`) REFERENCES `local_auth_accounts`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `idx_local_session_browser` ON `local_auth_sessions` (`browser`);--> statement-breakpoint
CREATE INDEX `idx_local_session_expiry` ON `local_auth_sessions` (`expires_at`);--> statement-breakpoint
CREATE INDEX `idx_local_session_account` ON `local_auth_sessions` (`account_id`);