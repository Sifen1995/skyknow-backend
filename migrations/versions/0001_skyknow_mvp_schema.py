import re

from alembic import op

revision = "0001_skyknow_mvp"
down_revision = None
branch_labels = None
depends_on = None


def _statements(sql: str):
    statements = []
    start = 0
    index = 0
    quote = None
    dollar_quote = None
    line_comment = False
    block_comment = False

    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif dollar_quote is not None:
            if sql.startswith(dollar_quote, index):
                index += len(dollar_quote) - 1
                dollar_quote = None
        elif quote is not None:
            if char == quote:
                if following == quote:
                    index += 1
                else:
                    quote = None
        elif char == "-" and following == "-":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in ("'", '"'):
            quote = char
        elif char == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$", sql[index:])
            if match:
                dollar_quote = match.group(0)
                index += len(dollar_quote) - 1
        elif char == ";":
            statement = sql[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1

        index += 1

    remainder = sql[start:].strip()
    if remainder:
        statements.append(remainder)
    return statements


SCHEMA_SQL = r"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS ltree;

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE TYPE role_name AS ENUM ('author', 'reviewer', 'publisher');
CREATE TYPE user_status AS ENUM ('active', 'disabled');
CREATE TYPE page_template AS ENUM ('howto', 'faq', 'policy');
CREATE TYPE visibility_scope AS ENUM ('all_staff', 'restricted');
CREATE TYPE version_state AS ENUM ('draft', 'in_review', 'approved', 'published', 'archived');
CREATE TYPE review_decision AS ENUM ('approved', 'rejected');
CREATE TYPE channel AS ENUM ('portal', 'agent_desktop', 'chatbot', 'voice', 'visual_ivr', 'support_app', 'api');
CREATE TYPE event_type AS ENUM ('page_view', 'search', 'search_click', 'insert', 'rating', 'comment');

CREATE TABLE languages (
  code text PRIMARY KEY CHECK (code ~ '^[a-z]{2,3}$'),
  name text NOT NULL UNIQUE,
  native_name text,
  is_active boolean NOT NULL DEFAULT true,
  sort_order smallint NOT NULL DEFAULT 0
);

CREATE TABLE org_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id uuid REFERENCES org_units(id) ON DELETE RESTRICT,
  label ltree NOT NULL CHECK (nlevel(label) = 1),
  name citext NOT NULL CHECK (length(btrim(name::text)) BETWEEN 1 AND 150),
  path ltree NOT NULL UNIQUE,
  head_user_id uuid,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX org_units_path_gist ON org_units USING gist (path);
CREATE INDEX org_units_parent_idx ON org_units (parent_id) WHERE parent_id IS NOT NULL;

CREATE FUNCTION org_units_set_path() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE parent_path ltree;
BEGIN
  IF NEW.parent_id IS NULL THEN
    NEW.path := NEW.label;
  ELSE
    SELECT path INTO parent_path FROM org_units WHERE id = NEW.parent_id;
    IF TG_OP = 'UPDATE' AND parent_path <@ OLD.path THEN
      RAISE EXCEPTION 'cannot move org unit % under itself or its own descendant', NEW.id
        USING ERRCODE = 'check_violation';
    END IF;
    NEW.path := parent_path || NEW.label;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER org_units_path_trg BEFORE INSERT OR UPDATE OF parent_id, label ON org_units
  FOR EACH ROW EXECUTE FUNCTION org_units_set_path();

CREATE FUNCTION org_units_repath_children() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE org_units SET label = label WHERE parent_id = NEW.id;
  RETURN NULL;
END $$;
CREATE TRIGGER org_units_repath_trg AFTER UPDATE OF path ON org_units
  FOR EACH ROW WHEN (OLD.path IS DISTINCT FROM NEW.path)
  EXECUTE FUNCTION org_units_repath_children();

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id text UNIQUE,
  email citext NOT NULL UNIQUE CHECK (email::text ~ '^[^@\s]+@[^@\s]+$'),
  full_name text NOT NULL CHECK (length(btrim(full_name)) > 0),
  status user_status NOT NULL DEFAULT 'active',
  is_admin boolean NOT NULL DEFAULT false,
  org_unit_id uuid NOT NULL REFERENCES org_units(id) ON DELETE RESTRICT,
  preferred_language text NOT NULL DEFAULT 'en' REFERENCES languages(code),
  last_login_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT users_id_unit_uq UNIQUE (id, org_unit_id)
);
CREATE INDEX users_unit_idx ON users (org_unit_id);
CREATE INDEX users_admin_idx ON users (id) WHERE is_admin AND status = 'active';
ALTER TABLE org_units ADD CONSTRAINT org_units_head_is_member
  FOREIGN KEY (head_user_id, id) REFERENCES users (id, org_unit_id)
  ON DELETE SET NULL (head_user_id);

CREATE TABLE tag_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name citext NOT NULL UNIQUE CHECK (length(btrim(name::text)) BETWEEN 1 AND 100),
  sort_order smallint NOT NULL DEFAULT 0
);
CREATE TABLE tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_group_id uuid NOT NULL REFERENCES tag_groups(id) ON DELETE RESTRICT,
  name citext NOT NULL CHECK (length(btrim(name::text)) BETWEEN 1 AND 100),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tags_unique_in_group UNIQUE (tag_group_id, name)
);

CREATE TABLE pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template page_template NOT NULL,
  owner_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  owner_org_unit_id uuid NOT NULL REFERENCES org_units(id) ON DELETE RESTRICT,
  visibility visibility_scope NOT NULL DEFAULT 'restricted',
  is_customer_visible boolean NOT NULL DEFAULT false,
  review_interval_months smallint CHECK (review_interval_months BETWEEN 1 AND 60),
  next_review_at timestamptz,
  created_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  archived_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pages_review_needs_interval
    CHECK (next_review_at IS NULL OR review_interval_months IS NOT NULL)
);
CREATE INDEX pages_owner_idx ON pages (owner_id);
CREATE INDEX pages_owner_unit_idx ON pages (owner_org_unit_id);
CREATE INDEX pages_created_by_idx ON pages (created_by);
CREATE INDEX pages_review_due_idx ON pages (next_review_at)
  WHERE archived_at IS NULL AND next_review_at IS NOT NULL;
CREATE INDEX pages_customer_idx ON pages (id)
  WHERE is_customer_visible AND archived_at IS NULL;

CREATE TABLE page_audiences (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  page_id uuid NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  org_unit_id uuid NOT NULL REFERENCES org_units(id) ON DELETE RESTRICT,
  include_descendants boolean NOT NULL DEFAULT true,
  CONSTRAINT page_audiences_unique UNIQUE (page_id, org_unit_id)
);
CREATE INDEX page_audiences_unit_idx ON page_audiences (org_unit_id);
CREATE TABLE page_tags (
  page_id uuid NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  tag_id uuid NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (page_id, tag_id)
);
CREATE INDEX page_tags_tag_idx ON page_tags (tag_id);

CREATE TABLE page_languages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id uuid NOT NULL REFERENCES pages(id) ON DELETE RESTRICT,
  language_code text NOT NULL REFERENCES languages(code) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT page_languages_unique UNIQUE (page_id, language_code),
  CONSTRAINT page_languages_ref_uq UNIQUE (id, page_id, language_code)
);

CREATE TABLE role_assignments (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role role_name NOT NULL,
  org_unit_id uuid NOT NULL REFERENCES org_units(id) ON DELETE RESTRICT,
  granted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  granted_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT role_assignments_unique UNIQUE (user_id, role, org_unit_id)
);
CREATE INDEX role_assignments_unit_idx ON role_assignments (org_unit_id);

CREATE FUNCTION user_has_role_for_page(p_user uuid, p_role role_name, p_page uuid)
RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT
    (p_role = 'publisher' AND EXISTS (
        SELECT 1 FROM users u WHERE u.id = p_user AND u.status = 'active' AND u.is_admin))
    OR EXISTS (
        SELECT 1
        FROM role_assignments ra
        JOIN users u ON u.id = ra.user_id AND u.status = 'active'
        JOIN org_units scope_unit ON scope_unit.id = ra.org_unit_id
        JOIN pages p ON p.id = p_page
        JOIN org_units owner_unit ON owner_unit.id = p.owner_org_unit_id
        WHERE ra.user_id = p_user
          AND ra.role = p_role
          AND owner_unit.path <@ scope_unit.path)
$$;

CREATE FUNCTION user_can_view_page(p_user uuid, p_page uuid)
RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT EXISTS (
    SELECT 1
    FROM users u
    JOIN org_units mine ON mine.id = u.org_unit_id
    JOIN pages p ON p.id = p_page AND p.archived_at IS NULL
    WHERE u.id = p_user AND u.status = 'active'
      AND (
        p.visibility = 'all_staff'
        OR EXISTS (
          SELECT 1
          FROM page_audiences pa
          JOIN org_units audience ON audience.id = pa.org_unit_id
          WHERE pa.page_id = p.id
            AND (mine.id = audience.id
              OR (pa.include_descendants AND mine.path <@ audience.path)
              OR (mine.head_user_id = u.id AND audience.path <@ mine.path))
        )
      )
  )
$$;

CREATE TABLE page_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_language_id uuid NOT NULL REFERENCES page_languages(id) ON DELETE RESTRICT,
  version_number integer NOT NULL CHECK (version_number > 0),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 300),
  summary text CHECK (summary IS NULL OR length(summary) <= 1000),
  content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
  content_text text NOT NULL DEFAULT '',
  state version_state NOT NULL DEFAULT 'draft',
  created_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  submitted_at timestamptz,
  approved_by uuid REFERENCES users(id) ON DELETE RESTRICT,
  approved_at timestamptz,
  published_at timestamptz,
  published_by uuid REFERENCES users(id) ON DELETE RESTRICT,
  scheduled_publish_at timestamptz,
  based_on_version_id uuid REFERENCES page_versions(id) ON DELETE RESTRICT,
  change_note text,
  is_ai_generated boolean NOT NULL DEFAULT false,
  ai_origin text CHECK (ai_origin IN ('generate', 'translate')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT page_versions_number_uq UNIQUE (page_language_id, version_number),
  CONSTRAINT page_versions_lang_ref_uq UNIQUE (id, page_language_id),
  CONSTRAINT pv_approver_not_author CHECK (approved_by IS NULL OR approved_by <> created_by),
  CONSTRAINT pv_submitted_when_past_draft CHECK (state = 'draft' OR submitted_at IS NOT NULL),
  CONSTRAINT pv_approval_recorded CHECK (state NOT IN ('approved', 'published') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
  CONSTRAINT pv_publish_recorded CHECK (state <> 'published' OR published_at IS NOT NULL),
  CONSTRAINT pv_ai_flag_matches_origin CHECK (is_ai_generated = (ai_origin IS NOT NULL))
);
CREATE UNIQUE INDEX page_versions_one_open_uq
  ON page_versions (page_language_id) WHERE state IN ('draft', 'in_review', 'approved');
CREATE UNIQUE INDEX page_versions_one_live_uq
  ON page_versions (page_language_id) WHERE state = 'published';
CREATE INDEX page_versions_author_idx ON page_versions (created_by);
CREATE INDEX page_versions_approver_idx ON page_versions (approved_by) WHERE approved_by IS NOT NULL;
CREATE INDEX page_versions_review_queue ON page_versions (submitted_at) WHERE state = 'in_review';
CREATE INDEX page_versions_scheduled_idx ON page_versions (scheduled_publish_at)
  WHERE state = 'approved' AND scheduled_publish_at IS NOT NULL;

CREATE FUNCTION page_versions_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_page_id uuid;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.state <> 'draft' THEN
      RAISE EXCEPTION 'only draft versions can be deleted (version %)', OLD.id
        USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF NEW.page_language_id <> OLD.page_language_id
     OR NEW.version_number <> OLD.version_number
     OR NEW.created_by <> OLD.created_by THEN
    RAISE EXCEPTION 'identity columns of a version are immutable'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.state <> 'draft'
     AND (NEW.title, NEW.summary, NEW.content, NEW.content_text)
         IS DISTINCT FROM (OLD.title, OLD.summary, OLD.content, OLD.content_text) THEN
    RAISE EXCEPTION 'content of a submitted version is frozen (version %)', OLD.id
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.state <> OLD.state AND NOT EXISTS (
    SELECT 1 FROM (VALUES
      ('draft', 'in_review'), ('draft', 'archived'), ('in_review', 'draft'),
      ('in_review', 'approved'), ('approved', 'published'), ('approved', 'archived'),
      ('published', 'archived')) AS allowed(from_state, to_state)
    WHERE allowed.from_state = OLD.state::text AND allowed.to_state = NEW.state::text
  ) THEN
    RAISE EXCEPTION 'illegal version state change % -> %', OLD.state, NEW.state
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.state <> OLD.state AND NEW.state IN ('approved', 'published') THEN
    SELECT page_id INTO v_page_id FROM page_languages WHERE id = NEW.page_language_id;
    IF NEW.state = 'approved'
       AND NOT user_has_role_for_page(NEW.approved_by, 'reviewer', v_page_id) THEN
      RAISE EXCEPTION 'approver does not hold the reviewer role for this page'
        USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.state = 'published' AND NEW.published_by IS NOT NULL
       AND NOT user_has_role_for_page(NEW.published_by, 'publisher', v_page_id) THEN
      RAISE EXCEPTION 'user does not hold the publisher role for this page'
        USING ERRCODE = 'insufficient_privilege';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER page_versions_guard_trg BEFORE UPDATE OR DELETE ON page_versions
  FOR EACH ROW EXECUTE FUNCTION page_versions_guard();

CREATE FUNCTION page_versions_check_author() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_page_id uuid;
BEGIN
  SELECT page_id INTO v_page_id FROM page_languages WHERE id = NEW.page_language_id;
  IF NOT user_has_role_for_page(NEW.created_by, 'author', v_page_id) THEN
    RAISE EXCEPTION 'user does not hold the author role for this page'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER page_versions_author_trg BEFORE INSERT ON page_versions
  FOR EACH ROW EXECUTE FUNCTION page_versions_check_author();

CREATE TABLE version_reviews (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  version_id uuid NOT NULL REFERENCES page_versions(id) ON DELETE RESTRICT,
  reviewer_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  decision review_decision NOT NULL,
  comment text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT vr_rejection_needs_comment
    CHECK (decision = 'approved' OR length(btrim(coalesce(comment, ''))) > 0)
);
CREATE INDEX version_reviews_version_idx ON version_reviews (version_id, created_at);
CREATE INDEX version_reviews_reviewer_idx ON version_reviews (reviewer_id);

CREATE TABLE comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id uuid NOT NULL REFERENCES pages(id) ON DELETE RESTRICT,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  parent_comment_id uuid,
  body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
  resolved_at timestamptz,
  resolved_by uuid REFERENCES users(id) ON DELETE RESTRICT,
  edited_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT comments_id_page_uq UNIQUE (id, page_id),
  CONSTRAINT comments_parent_same_page FOREIGN KEY (parent_comment_id, page_id)
    REFERENCES comments (id, page_id) ON DELETE RESTRICT,
  CONSTRAINT comments_resolve_pair CHECK ((resolved_at IS NULL) = (resolved_by IS NULL)),
  CONSTRAINT comments_only_threads_resolve CHECK (parent_comment_id IS NULL OR resolved_at IS NULL)
);
CREATE INDEX comments_page_idx ON comments (page_id, created_at);
CREATE INDEX comments_parent_idx ON comments (parent_comment_id) WHERE parent_comment_id IS NOT NULL;
CREATE INDEX comments_user_idx ON comments (user_id);
CREATE INDEX comments_open_idx ON comments (page_id)
  WHERE parent_comment_id IS NULL AND resolved_at IS NULL AND deleted_at IS NULL;

CREATE TABLE page_ratings (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  page_id uuid NOT NULL REFERENCES pages(id) ON DELETE RESTRICT,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  stars smallint CHECK (stars BETWEEN 1 AND 5),
  helpful boolean,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT page_ratings_one_per_user UNIQUE (page_id, user_id),
  CONSTRAINT page_ratings_has_value CHECK (stars IS NOT NULL OR helpful IS NOT NULL)
);
CREATE INDEX page_ratings_user_idx ON page_ratings (user_id);

CREATE TABLE chunks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  page_version_id uuid NOT NULL,
  page_language_id uuid NOT NULL,
  page_id uuid NOT NULL,
  language_code text NOT NULL,
  chunk_index integer NOT NULL CHECK (chunk_index >= 0),
  heading_path text NOT NULL DEFAULT '',
  section_anchor text,
  body text NOT NULL CHECK (length(btrim(body)) > 0),
  token_count integer NOT NULL CHECK (token_count > 0),
  embedding vector(1536) NOT NULL,
  embedding_model text NOT NULL,
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', heading_path || ' ' || body)) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chunks_position_uq UNIQUE (page_version_id, chunk_index),
  CONSTRAINT chunks_version_fk FOREIGN KEY (page_version_id, page_language_id)
    REFERENCES page_versions (id, page_language_id) ON DELETE CASCADE,
  CONSTRAINT chunks_lang_fk FOREIGN KEY (page_language_id, page_id, language_code)
    REFERENCES page_languages (id, page_id, language_code) ON DELETE CASCADE
);
CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX chunks_page_idx ON chunks (page_id);
CREATE INDEX chunks_pagelang_idx ON chunks (page_language_id);
CREATE INDEX chunks_language_idx ON chunks (language_code);

CREATE TABLE events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  channel channel NOT NULL,
  event_type event_type NOT NULL,
  page_id uuid REFERENCES pages(id) ON DELETE SET NULL,
  page_version_id uuid REFERENCES page_versions(id) ON DELETE SET NULL,
  query_text text,
  result_count integer CHECK (result_count >= 0),
  metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
  CONSTRAINT events_page_required
    CHECK (event_type NOT IN ('page_view', 'search_click', 'insert') OR page_id IS NOT NULL),
  CONSTRAINT events_query_required
    CHECK (event_type <> 'search' OR (query_text IS NOT NULL AND result_count IS NOT NULL))
);
CREATE INDEX events_time_brin ON events USING brin (occurred_at);
CREATE INDEX events_page_time_idx ON events (page_id, occurred_at) WHERE page_id IS NOT NULL;
CREATE INDEX events_zero_result_idx ON events (occurred_at)
  WHERE event_type = 'search' AND result_count = 0;

CREATE TABLE audit_log (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_id uuid REFERENCES users(id) ON DELETE RESTRICT,
  action text NOT NULL CHECK (length(action) > 0),
  object_type text NOT NULL CHECK (length(object_type) > 0),
  object_id text NOT NULL,
  page_id uuid,
  version_id uuid,
  before jsonb,
  after jsonb,
  request_id text,
  ip_address inet
);
CREATE INDEX audit_page_idx ON audit_log (page_id, occurred_at DESC) WHERE page_id IS NOT NULL;
CREATE INDEX audit_actor_idx ON audit_log (actor_id, occurred_at DESC) WHERE actor_id IS NOT NULL;
CREATE INDEX audit_time_brin ON audit_log USING brin (occurred_at);
CREATE FUNCTION audit_log_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = 'insufficient_privilege';
END $$;
CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only();

CREATE TABLE ai_request_log (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  feature text NOT NULL CHECK (feature IN ('embedding', 'chat', 'generate', 'translate', 'summary')),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  page_version_id uuid REFERENCES page_versions(id) ON DELETE SET NULL,
  provider text NOT NULL,
  model text NOT NULL,
  status text NOT NULL CHECK (status IN ('ok', 'error', 'timeout', 'rate_limited', 'blocked')),
  redacted_input text,
  output text,
  redaction_count integer NOT NULL DEFAULT 0 CHECK (redaction_count >= 0),
  input_tokens integer CHECK (input_tokens >= 0),
  output_tokens integer CHECK (output_tokens >= 0),
  cost_usd numeric(12, 6) CHECK (cost_usd >= 0),
  latency_ms integer CHECK (latency_ms >= 0),
  error_code text
);
CREATE INDEX ai_log_time_brin ON ai_request_log USING brin (occurred_at);
CREATE INDEX ai_log_feature_idx ON ai_request_log (feature, occurred_at);
CREATE INDEX ai_log_user_idx ON ai_request_log (user_id, occurred_at) WHERE user_id IS NOT NULL;

CREATE TRIGGER trg_updated_at BEFORE UPDATE ON org_units
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_updated_at BEFORE UPDATE ON pages
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_updated_at BEFORE UPDATE ON page_versions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_updated_at BEFORE UPDATE ON comments
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_updated_at BEFORE UPDATE ON page_ratings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO languages (code, name, native_name, sort_order) VALUES
  ('en', 'English', 'English', 1),
  ('am', 'Amharic', 'አማርኛ', 2),
  ('om', 'Oromo', 'Afaan Oromoo', 3);
INSERT INTO tag_groups (name, sort_order) VALUES
  ('Product', 1), ('Process', 2), ('Fault', 3);
"""


def upgrade() -> None:
    for statement in _statements(SCHEMA_SQL):
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS ai_request_log, audit_log, events, chunks, page_ratings, "
        "comments, version_reviews, page_versions, role_assignments, page_languages, "
        "page_tags, page_audiences, pages, tags, tag_groups, users, org_units, languages "
        "CASCADE"
    )
    for statement in (
        "DROP FUNCTION IF EXISTS audit_log_append_only() CASCADE",
        "DROP FUNCTION IF EXISTS page_versions_check_author() CASCADE",
        "DROP FUNCTION IF EXISTS page_versions_guard() CASCADE",
        "DROP FUNCTION IF EXISTS user_can_view_page(uuid, uuid) CASCADE",
        "DROP FUNCTION IF EXISTS user_has_role_for_page(uuid, role_name, uuid) CASCADE",
        "DROP FUNCTION IF EXISTS org_units_repath_children() CASCADE",
        "DROP FUNCTION IF EXISTS org_units_set_path() CASCADE",
        "DROP FUNCTION IF EXISTS set_updated_at() CASCADE",
        "DROP TYPE IF EXISTS event_type CASCADE",
        "DROP TYPE IF EXISTS channel CASCADE",
        "DROP TYPE IF EXISTS review_decision CASCADE",
        "DROP TYPE IF EXISTS version_state CASCADE",
        "DROP TYPE IF EXISTS visibility_scope CASCADE",
        "DROP TYPE IF EXISTS page_template CASCADE",
        "DROP TYPE IF EXISTS user_status CASCADE",
        "DROP TYPE IF EXISTS role_name CASCADE",
    ):
        op.execute(statement)
