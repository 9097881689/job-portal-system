CREATE TABLE IF NOT EXISTS processed_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name VARCHAR(160) NOT NULL,
    source_job_id VARCHAR(255) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL UNIQUE,
    canonical_key VARCHAR(64) NOT NULL UNIQUE,
    content_hash VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    source_url TEXT NOT NULL,
    source_priority INTEGER NOT NULL DEFAULT 100,
    status VARCHAR(40) NOT NULL DEFAULT 'collected',
    blogger_post_id VARCHAR(120),
    blogger_url TEXT,
    error_message TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_processed_jobs_source_name ON processed_jobs(source_name);
CREATE INDEX IF NOT EXISTS ix_processed_jobs_source_job_id ON processed_jobs(source_job_id);
CREATE INDEX IF NOT EXISTS ix_processed_jobs_canonical_key ON processed_jobs(canonical_key);
CREATE INDEX IF NOT EXISTS ix_processed_jobs_content_hash ON processed_jobs(content_hash);
CREATE INDEX IF NOT EXISTS ix_processed_jobs_status ON processed_jobs(status);

CREATE TABLE IF NOT EXISTS published_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processed_job_id INTEGER NOT NULL,
    blogger_post_id VARCHAR(120),
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    labels TEXT NOT NULL,
    canonical_url TEXT,
    content_hash VARCHAR(64),
    source_url TEXT,
    created_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_published_posts_processed_job_id ON published_posts(processed_job_id);
CREATE INDEX IF NOT EXISTS ix_published_posts_slug ON published_posts(slug);
