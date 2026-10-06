CREATE TABLE `publication_requests` (
	`id` text PRIMARY KEY NOT NULL,
	`report_id` text NOT NULL,
	`payload_hash` text NOT NULL,
	`kind` text NOT NULL,
	`state` text DEFAULT 'requested' NOT NULL,
	`actor_id` text NOT NULL,
	`created_at` integer NOT NULL
);
