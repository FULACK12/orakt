CREATE TABLE `protocol_orders` (
	`order_id` text PRIMARY KEY NOT NULL,
	`policy_json` text NOT NULL,
	`binding_json` text NOT NULL,
	`invoice` text NOT NULL,
	`receipt` text NOT NULL,
	`subscription` text NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_protocol_order_receipt` ON `protocol_orders` (`receipt`);--> statement-breakpoint
CREATE TABLE `protocol_settlements` (
	`receipt` text PRIMARY KEY NOT NULL,
	`order_id` text NOT NULL,
	`signature` text NOT NULL,
	`member_id` text NOT NULL,
	`proof_json` text NOT NULL,
	`settled_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_protocol_settlement_order` ON `protocol_settlements` (`order_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `idx_protocol_settlement_signature` ON `protocol_settlements` (`signature`);--> statement-breakpoint
ALTER TABLE `billing_orders` ADD `payment_method` text DEFAULT 'spl_transfer' NOT NULL;