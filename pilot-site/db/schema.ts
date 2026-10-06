import { index, integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";
export const intelligenceItems=sqliteTable('intelligence_items',{
 id:text('id').primaryKey(),authorId:text('author_id').notNull(),kind:text('kind').notNull(),payload:text('payload').notNull(),contentHash:text('content_hash').notNull(),assetKey:text('asset_key'),state:text('state').notNull().default('pending'),verdict:text('verdict').notNull().default('unresolved'),revision:integer('revision').notNull().default(0),headHash:text('head_hash').notNull(),createdAt:integer('created_at').notNull(),
},t=>[uniqueIndex('idx_intelligence_content').on(t.contentHash),index('idx_intelligence_author').on(t.authorId,t.createdAt)]);
export const intelligenceHistory=sqliteTable('intelligence_history',{
 id:text('id').primaryKey(),itemId:text('item_id').notNull(),revision:integer('revision').notNull(),record:text('record').notNull(),hash:text('hash').notNull(),previousHash:text('previous_hash'),createdAt:integer('created_at').notNull(),
},t=>[uniqueIndex('idx_intelligence_revision').on(t.itemId,t.revision)]);
export const intelligenceAnchors=sqliteTable('intelligence_anchors',{
 itemId:text('item_id').notNull(),revision:integer('revision').notNull(),headHash:text('head_hash').notNull(),wallet:text('wallet').notNull(),signature:text('signature'),createdAt:integer('created_at').notNull(),
},t=>[uniqueIndex('idx_intelligence_anchor').on(t.itemId,t.revision)]);
export const newsSubmissions=sqliteTable("news_submissions",{
 id:text("id").primaryKey(),authorId:text("author_id").notNull(),title:text("title").notNull(),body:text("body").notNull(),sourceUrls:text("source_urls").notNull(),eventDate:text("event_date").notNull(),contentHash:text("content_hash").notNull(),state:text("state").notNull().default("pending"),reviewNote:text("review_note"),reviewerId:text("reviewer_id"),reviewedAt:integer("reviewed_at"),wallet:text("wallet"),signature:text("signature"),createdAt:integer("created_at").notNull(),
},t=>[index("idx_news_author_created").on(t.authorId,t.createdAt),uniqueIndex("idx_news_author_hash").on(t.authorId,t.contentHash)]);
export const publicationRequests=sqliteTable("publication_requests",{
 id:text("id").primaryKey(),reportId:text("report_id").notNull(),payloadHash:text("payload_hash").notNull(),kind:text("kind").notNull(),state:text("state").notNull().default("requested"),actorId:text("actor_id").notNull(),createdAt:integer("created_at").notNull(),
});

export const memberAccounts=sqliteTable("member_accounts",{
 id:text("id").primaryKey(),provider:text("provider").notNull(),subject:text("subject").notNull(),displayName:text("display_name").notNull(),legacyRef:text("legacy_ref").notNull(),
 createdAt:integer("created_at").notNull(),firstSeenAt:integer("first_seen_at").notNull(),lastSeenAt:integer("last_seen_at"),
 status:text("status").notNull().default("active"),plan:text("plan").notNull().default("explorer"),grantKind:text("grant_kind").notNull().default("free"),expiresAt:integer("expires_at"),revision:integer("revision").notNull().default(0),lastChangeId:text("last_change_id").notNull().default(""),
},t=>[uniqueIndex("idx_member_provider_subject").on(t.provider,t.subject),index("idx_member_last_seen").on(t.lastSeenAt),index("idx_member_created").on(t.createdAt)]);
export const memberAudit=sqliteTable("member_audit",{
 id:text("id").primaryKey(),actorId:text("actor_id").notNull(),targetId:text("target_id").notNull(),beforeJson:text("before_json").notNull(),afterJson:text("after_json").notNull(),reason:text("reason").notNull(),createdAt:integer("created_at").notNull(),
},t=>[index("idx_member_audit_target_created").on(t.targetId,t.createdAt),index("idx_member_audit_created").on(t.createdAt)]);

export const localAuthAccounts=sqliteTable("local_auth_accounts",{
  id:text("id").primaryKey(),username:text("username").notNull(),salt:text("salt").notNull(),
  passwordHash:text("password_hash").notNull(),kdf:text("kdf").notNull(),recoveryHash:text("recovery_hash").notNull(),
  authVersion:text("auth_version").notNull(),createdAt:integer("created_at").notNull(),
},t=>[uniqueIndex("idx_local_account_username").on(t.username)]);
export const localAuthChallenges=sqliteTable("local_auth_challenges",{
  nonce:text("nonce").primaryKey(),csrf:text("csrf").notNull(),browser:text("browser").notNull(),origin:text("origin").notNull(),action:text("action").notNull(),expiresAt:integer("expires_at").notNull(),
},t=>[index("idx_local_challenge_browser").on(t.browser),index("idx_local_challenge_expiry").on(t.expiresAt)]);
export const localAuthSessions=sqliteTable("local_auth_sessions",{
  id:text("id").primaryKey(),browser:text("browser").notNull(),accountId:text("account_id").notNull().references(()=>localAuthAccounts.id),authVersion:text("auth_version").notNull(),origin:text("origin").notNull(),expiresAt:integer("expires_at").notNull(),
},t=>[index("idx_local_session_browser").on(t.browser),index("idx_local_session_expiry").on(t.expiresAt),index("idx_local_session_account").on(t.accountId)]);

export const googleAuthChallenges = sqliteTable("google_auth_challenges", {
  nonce:text("nonce").primaryKey(), csrf:text("csrf").notNull(), browser:text("browser").notNull(),
  origin:text("origin").notNull(), expiresAt:integer("expires_at").notNull(),
},table=>[index("idx_google_challenge_browser").on(table.browser),index("idx_google_challenge_expiry").on(table.expiresAt)]);
export const googleAuthSessions = sqliteTable("google_auth_sessions", {
  id:text("id").primaryKey(), browser:text("browser").notNull(), subject:text("subject").notNull(),
  origin:text("origin").notNull(), expiresAt:integer("expires_at").notNull(),
},table=>[index("idx_google_session_browser").on(table.browser),index("idx_google_session_expiry").on(table.expiresAt)]);

// Ephemeral, server-issued wallet challenges. No private keys or balances stored.
export const walletAuthChallenges = sqliteTable("wallet_auth_challenges", {
  nonce: text("nonce").primaryKey(),
  browser: text("browser").notNull(),
  address: text("address").notNull(),
  origin: text("origin").notNull(),
  message: text("message").notNull(),
  expiresAt: integer("expires_at").notNull(),
}, table => [index("idx_wallet_challenge_expiry").on(table.expiresAt), index("idx_wallet_challenge_browser").on(table.browser)]);

export const walletAuthLimits = sqliteTable("wallet_auth_limits", {
  bucket: text("bucket").primaryKey(),
  count: integer("count").notNull(),
  expiresAt: integer("expires_at").notNull(),
}, table => [index("idx_wallet_limit_expiry").on(table.expiresAt)]);

export const walletAuthSessions = sqliteTable("wallet_auth_sessions", {
  id: text("id").primaryKey(),
  browser: text("browser").notNull().default(""),
  expiresAt: integer("expires_at").notNull(),
}, table => [index("idx_wallet_session_expiry").on(table.expiresAt), index("idx_wallet_session_browser").on(table.browser)]);

export const evidenceReports = sqliteTable(
  "evidence_reports",
  {
    id: text("id").primaryKey(),
    question: text("question").notNull(),
    reportJson: text("report_json").notNull(),
    model: text("model").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("idx_evidence_reports_created_at").on(table.createdAt)],
);

export const reviewFeedback = sqliteTable(
  "review_feedback",
  {
    id: text("id").primaryKey(),
    reportId: text("report_id").notNull(),
    question: text("question").notNull(),
    decision: text("decision").notNull(),
    comment: text("comment").notNull().default(""),
    confidence: integer("confidence").notNull().default(0),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("idx_review_feedback_report_created").on(table.reportId, table.createdAt),
  ],
);
