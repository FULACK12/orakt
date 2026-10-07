CREATE TABLE `member_watchlists` (
	`member_id` text PRIMARY KEY NOT NULL,
	`tickers` text DEFAULT '[]' NOT NULL,
	`updated_at` integer NOT NULL,
	FOREIGN KEY (`member_id`) REFERENCES `member_accounts`(`id`) ON UPDATE no action ON DELETE no action
);
