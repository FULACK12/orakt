CREATE TABLE `account_wallet_audit` (
	`id` text PRIMARY KEY NOT NULL,
	`member_id` text NOT NULL,
	`address` text NOT NULL,
	`action` text NOT NULL,
	`message` text NOT NULL,
	`signature` text NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_account_wallet_audit_member` ON `account_wallet_audit` (`member_id`,`created_at`);--> statement-breakpoint
CREATE TABLE `account_wallet_challenges` (
	`nonce` text PRIMARY KEY NOT NULL,
	`browser` text NOT NULL,
	`member_id` text NOT NULL,
	`member_revision` integer NOT NULL,
	`address` text NOT NULL,
	`action` text NOT NULL,
	`origin` text NOT NULL,
	`message` text NOT NULL,
	`expires_at` integer NOT NULL,
	`expected_change_id` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_account_wallet_challenge_browser` ON `account_wallet_challenges` (`browser`);--> statement-breakpoint
CREATE INDEX `idx_account_wallet_challenge_expiry` ON `account_wallet_challenges` (`expires_at`);--> statement-breakpoint
CREATE TABLE `account_wallet_links` (
	`address` text PRIMARY KEY NOT NULL,
	`member_id` text NOT NULL,
	`active_member_key` text,
	`verified_at` integer NOT NULL,
	`revoked_at` integer,
	`change_id` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_wallet_link_active_member` ON `account_wallet_links` (`active_member_key`);