CREATE TABLE `evidence_reports` (
	`id` text PRIMARY KEY NOT NULL,
	`question` text NOT NULL,
	`report_json` text NOT NULL,
	`model` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `review_feedback` (
	`id` text PRIMARY KEY NOT NULL,
	`report_id` text NOT NULL,
	`question` text NOT NULL,
	`decision` text NOT NULL,
	`comment` text DEFAULT '' NOT NULL,
	`confidence` integer DEFAULT 0 NOT NULL,
	`created_at` text NOT NULL
);
