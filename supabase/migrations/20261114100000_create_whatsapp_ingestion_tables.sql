-- =============================================================================
-- HERAI PHASE 2: WHATSAPP DATA ENGINEERING SCHEMA MIGRATION
-- Tables: source_archives, conversation_sessions, source_messages, analysis_jobs
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. SOURCE ARCHIVES
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.source_archives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archive_filename TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL UNIQUE,
    file_size_bytes BIGINT NOT NULL,
    total_lines_detected INTEGER DEFAULT 0,
    total_records_parsed INTEGER DEFAULT 0,
    earliest_message_timestamp TIMESTAMPTZ,
    latest_message_timestamp TIMESTAMPTZ,
    status VARCHAR(30) DEFAULT 'processed' CHECK (status IN ('pending', 'processing', 'processed', 'failed')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.source_archives ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read on source_archives"
    ON public.source_archives FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access on source_archives"
    ON public.source_archives FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_source_archives_file_hash ON public.source_archives(file_hash);

-- -----------------------------------------------------------------------------
-- 2. CONVERSATION SESSIONS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL UNIQUE,
    start_timestamp TIMESTAMPTZ NOT NULL,
    end_timestamp TIMESTAMPTZ NOT NULL,
    inactivity_threshold_hours REAL NOT NULL DEFAULT 6.0,
    message_count INTEGER NOT NULL DEFAULT 0,
    partner_message_count INTEGER NOT NULL DEFAULT 0,
    user_message_count INTEGER NOT NULL DEFAULT 0,
    source_archive_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.conversation_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read on conversation_sessions"
    ON public.conversation_sessions FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access on conversation_sessions"
    ON public.conversation_sessions FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON public.conversation_sessions(start_timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_end_time ON public.conversation_sessions(end_timestamp);

-- -----------------------------------------------------------------------------
-- 3. SOURCE MESSAGES
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.source_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archive_id UUID NOT NULL REFERENCES public.source_archives(id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.conversation_sessions(session_id) ON DELETE SET NULL,
    source_message_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    sender VARCHAR(20) NOT NULL CHECK (sender IN ('partner', 'user', 'system')),
    original_sender TEXT NOT NULL,
    body TEXT NOT NULL,
    message_type VARCHAR(30) NOT NULL CHECK (message_type IN ('text', 'media', 'deleted', 'call_log', 'system', 'empty_placeholder')),
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('image', 'video', 'audio', 'sticker', 'document', 'gif', 'contact', 'none')),
    is_system_message BOOLEAN NOT NULL DEFAULT FALSE,
    is_multiline BOOLEAN NOT NULL DEFAULT FALSE,
    source_line_number INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    is_duplicate_across_archives BOOLEAN NOT NULL DEFAULT FALSE,
    duplicate_archive_provenance JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_archive_source_msg UNIQUE (archive_id, source_message_id)
);

ALTER TABLE public.source_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read on source_messages"
    ON public.source_messages FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access on source_messages"
    ON public.source_messages FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_source_messages_timestamp ON public.source_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_source_messages_sender ON public.source_messages(sender);
CREATE INDEX IF NOT EXISTS idx_source_messages_session ON public.source_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_source_messages_content_hash ON public.source_messages(content_hash);
CREATE INDEX IF NOT EXISTS idx_source_messages_archive_id ON public.source_messages(archive_id);
CREATE INDEX IF NOT EXISTS idx_source_messages_type ON public.source_messages(message_type);

-- -----------------------------------------------------------------------------
-- 4. ANALYSIS JOBS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    archives_processed JSONB DEFAULT '[]'::jsonb,
    quality_metrics JSONB DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE public.analysis_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read on analysis_jobs"
    ON public.analysis_jobs FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access on analysis_jobs"
    ON public.analysis_jobs FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
