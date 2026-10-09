CREATE TABLE `billing_orders` (
	`id` text PRIMARY KEY NOT NULL,
	`member_id` text NOT NULL,
	`plan` text NOT NULL,
	`currency` text NOT NULL,
	`network` text NOT NULL,
	`mint` text NOT NULL,
	`recipient` text NOT NULL,
	`payer` text NOT NULL,
	`reference` text NOT NULL,
	`amount_units` text NOT NULL,
	`created_at` integer NOT NULL,
	`expires_at` integer NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`signature` text,
	`paid_at` integer,
	`access_from` integer,
	`access_until` integer,
	`settlement_revision` integer,
	`active_member_key` text,
	FOREIGN KEY (`member_id`) REFERENCES `member_accounts`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_billing_reference` ON `billing_orders` (`reference`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_billing_signature` ON `billing_orders` (`signature`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_billing_active_member` ON `billing_orders` (`active_member_key`);--> statement-breakpoint
CREATE INDEX `idx_billing_member_created` ON `billing_orders` (`member_id`,`created_at`);