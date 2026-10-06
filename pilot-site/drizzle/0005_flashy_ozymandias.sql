CREATE TABLE `google_auth_challenges` (
	`nonce` text PRIMARY KEY NOT NULL,
	`csrf` text NOT NULL,
	`browser` text NOT NULL,
	`origin` text NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_google_challenge_browser` ON `google_auth_challenges` (`browser`);--> statement-breakpoint
CREATE INDEX `idx_google_challenge_expiry` ON `google_auth_challenges` (`expires_at`);--> statement-breakpoint
CREATE TABLE `google_auth_sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`browser` text NOT NULL,
	`subject` text NOT NULL,
	`origin` text NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_google_session_browser` ON `google_auth_sessions` (`browser`);--> statement-breakpoint
CREATE INDEX `idx_google_session_expiry` ON `google_auth_sessions` (`expires_at`);