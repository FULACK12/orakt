// Preserve class-share ticker dots only in the versioned dossier grammar.
// Never permit arbitrary dots, path separators or URL metacharacters in filenames.
export const isSafeReportIdentifier = value => typeof value === 'string' && (
 /^[A-Za-z0-9_-]+$/.test(value) ||
 /^dossier-[A-Z]{1,8}(?:\.[A-Z]{1,3})-\d{8}-[a-f0-9]{8}$/.test(value)
);
