CREATE TABLE `intelligence_anchors` (
	`item_id` text NOT NULL,
	`revision` integer NOT NULL,
	`head_hash` text NOT NULL,
	`wallet` text NOT NULL,
	`signature` text,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_intelligence_anchor` ON `intelligence_anchors` (`item_id`,`revision`);--> statement-breakpoint
CREATE TABLE `intelligence_history` (
	`id` text PRIMARY KEY NOT NULL,
	`item_id` text NOT NULL,
	`revision` integer NOT NULL,
	`record` text NOT NULL,
	`hash` text NOT NULL,
	`previous_hash` text,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_intelligence_revision` ON `intelligence_history` (`item_id`,`revision`);--> statement-breakpoint
CREATE TABLE `intelligence_items` (
	`id` text PRIMARY KEY NOT NULL,
	`author_id` text NOT NULL,
	`kind` text NOT NULL,
	`payload` text NOT NULL,
	`content_hash` text NOT NULL,
	`asset_key` text,
	`state` text DEFAULT 'pending' NOT NULL,
	`verdict` text DEFAULT 'unresolved' NOT NULL,
	`revision` integer DEFAULT 0 NOT NULL,
	`head_hash` text NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_intelligence_content` ON `intelligence_items` (`content_hash`);--> statement-breakpoint
CREATE INDEX `idx_intelligence_author` ON `intelligence_items` (`author_id`,`created_at`);