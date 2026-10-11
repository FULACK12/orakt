CREATE TABLE `report_provenance` (
	`id` text PRIMARY KEY NOT NULL,
	`report_id` text NOT NULL,
	`network` text NOT NULL,
	`wallet` text NOT NULL,
	`actor_id` text NOT NULL,
	`signature` text,
	`created_at` integer NOT NULL,
	`confirmed_at` integer
);
--> statement-breakpoint
CREATE TABLE `research_jobs` (
	`id` text PRIMARY KEY NOT NULL,
	`actor_id` text NOT NULL,
	`prompt` text NOT NULL,
	`language` text NOT NULL,
	`evidence` text NOT NULL,
	`state` text NOT NULL,
	`result` text,
	`error` text,
	`lease_token` text,
	`lease_until` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_research_jobs_actor_created` ON `research_jobs` (`actor_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `idx_research_jobs_state` ON `research_jobs` (`state`,`created_at`);--> statement-breakpoint
CREATE TABLE `research_worker` (
	`id` integer PRIMARY KEY NOT NULL,
	`status` text NOT NULL,
	`updated_at` integer NOT NULL
);
