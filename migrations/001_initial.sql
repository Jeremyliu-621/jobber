CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_job_id TEXT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT NOT NULL,
    apply_url TEXT,
    description_text TEXT NOT NULL DEFAULT '',
    posted_at TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'discovered',
    dedupe_hash TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (source, source_job_id),
    UNIQUE (dedupe_hash)
);

CREATE TABLE IF NOT EXISTS job_criteria (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    weight REAL NOT NULL,
    source_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS candidate_sources (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0 CHECK (approved IN (0, 1)),
    source TEXT NOT NULL DEFAULT 'unknown',
    topics_json TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    last_indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS criterion_evidence (
    id TEXT PRIMARY KEY,
    criterion_id TEXT NOT NULL REFERENCES job_criteria(id) ON DELETE CASCADE,
    candidate_source_id TEXT NOT NULL REFERENCES candidate_sources(id) ON DELETE CASCADE,
    strength REAL NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS job_evaluations (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    eligibility_status TEXT NOT NULL,
    fit_score REAL,
    importance_score REAL,
    tier TEXT,
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_id TEXT,
    version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    rendered_path TEXT,
    version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    tier TEXT NOT NULL,
    resume_id TEXT REFERENCES resumes(id),
    browser_provider TEXT,
    browser_session_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    submitted_at TEXT,
    last_updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_questions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    question_type TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
    max_length INTEGER,
    source_page TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_answers (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES application_questions(id) ON DELETE CASCADE,
    generated_text TEXT,
    final_text TEXT,
    status TEXT NOT NULL,
    grounding_score REAL,
    style_score REAL,
    human_edit_distance REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS answer_claims (
    id TEXT PRIMARY KEY,
    answer_id TEXT NOT NULL REFERENCES application_answers(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    candidate_source_id TEXT NOT NULL REFERENCES candidate_sources(id),
    support_type TEXT NOT NULL,
    confidence REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS application_events (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id TEXT PRIMARY KEY,
    application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    original_text TEXT NOT NULL,
    edited_text TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS candidate_sources_fts USING fts5(
    source_id UNINDEXED,
    title,
    topics,
    content
);

