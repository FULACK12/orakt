CREATE TABLE `news_submissions` (
	`id` text PRIMARY KEY NOT NULL,
	`author_id` text NOT NULL,
	`title` text NOT NULL,
	`body` text NOT NULL,
	`source_urls` text NOT NULL,
	`event_date` text NOT NULL,
	`content_hash` text NOT NULL,
	`state` text DEFAULT 'pending' NOT NULL,
	`review_note` text,
	`reviewer_id` text,
	`reviewed_at` integer,
	`wallet` text,
	`signature` text,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_news_author_created` ON `news_submissions` (`author_id`,`created_at`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_news_author_hash` ON `news_submissions` (`author_id`,`content_hash`);