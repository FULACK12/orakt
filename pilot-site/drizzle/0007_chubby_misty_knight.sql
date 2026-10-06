CREATE TABLE `member_accounts` (
	`id` text PRIMARY KEY NOT NULL,
	`provider` text NOT NULL,
	`subject` text NOT NULL,
	`display_name` text NOT NULL,
	`legacy_ref` text NOT NULL,
	`created_at` integer NOT NULL,
	`first_seen_at` integer NOT NULL,
	`last_seen_at` integer,
	`status` text DEFAULT 'active' NOT NULL,
	`plan` text DEFAULT 'explorer' NOT NULL,
	`grant_kind` text DEFAULT 'free' NOT NULL,
	`expires_at` integer,
	`revision` integer DEFAULT 0 NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_member_provider_subject` ON `member_accounts` (`provider`,`subject`);--> statement-breakpoint
CREATE INDEX `idx_member_last_seen` ON `member_accounts` (`last_seen_at`);--> statement-breakpoint
CREATE INDEX `idx_member_created` ON `member_accounts` (`created_at`);--> statement-breakpoint
CREATE TABLE `member_audit` (
	`id` text PRIMARY KEY NOT NULL,
	`actor_id` text NOT NULL,
	`target_id` text NOT NULL,
	`before_json` text NOT NULL,
	`after_json` text NOT NULL,
	`reason` text NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_member_audit_target_created` ON `member_audit` (`target_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `idx_member_audit_created` ON `member_audit` (`created_at`);