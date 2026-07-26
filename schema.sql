-- Palate schema. FROZEN at the base commit.
-- Additive changes only (new nullable columns / new tables), and announce them.
-- Anything destructive breaks another owner's branch mid-flight.

CREATE TABLE IF NOT EXISTS raw_message (
  id             TEXT PRIMARY KEY,   -- provider message id
  source         TEXT NOT NULL,      -- gmail | calendar
  sender         TEXT,
  subject        TEXT,
  body           TEXT,
  received_at    TEXT,
  matched_vendor TEXT,               -- set by the pre-filter; NULL = dropped
  extracted      INTEGER DEFAULT 0,  -- 0 = pending extraction
  fetched_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_pending ON raw_message(extracted, matched_vendor);

CREATE TABLE IF NOT EXISTS visit (
  id              TEXT PRIMARY KEY,  -- contracts.visit_id(), deterministic
  source          TEXT NOT NULL,     -- gmail | calendar | drive_exif | notion
  source_ref      TEXT,
  vendor          TEXT,
  place_name_raw  TEXT NOT NULL,
  place_id        TEXT,
  city            TEXT,
  category        TEXT,              -- restaurant | bar | event | lodging | activity
  cuisine         TEXT,              -- JSON array
  price_band      INTEGER,           -- 1..4
  party_size      INTEGER,
  scheduled_at    TEXT,              -- ISO local wall-clock 'YYYY-MM-DDTHH:MM' (NO timezone)
  booked_at       TEXT,
  status          TEXT NOT NULL,     -- confirmed | cancelled | modified | attended_unbooked
  cancelled_at    TEXT,
  is_travel       INTEGER DEFAULT 0,
  intent_only     INTEGER DEFAULT 0,
  seat            TEXT,              -- bar | table | unknown
  raw_total_cents INTEGER,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_visit_sched  ON visit(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_visit_status ON visit(status);
CREATE INDEX IF NOT EXISTS idx_visit_place  ON visit(place_name_raw);

CREATE TABLE IF NOT EXISTS taste_profile (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  computed_at TEXT NOT NULL,
  payload     TEXT NOT NULL          -- JSON, keys per contracts.TASTE_PROFILE_KEYS
);

CREATE TABLE IF NOT EXISTS place_cache (
  query      TEXT PRIMARY KEY,       -- normalized 'name|city'
  payload    TEXT NOT NULL,          -- JSON from Google Places
  fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itinerary (
  id         TEXT PRIMARY KEY,
  city       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload    TEXT NOT NULL           -- JSON, shape per TRD 3.3
);

CREATE TABLE IF NOT EXISTS session (
  phone        TEXT PRIMARY KEY,
  itinerary_id TEXT,
  state        TEXT,                 -- JSON scratch for the chat layer
  updated_at   TEXT NOT NULL
);

-- Spend tracking against the $20 Merge Gateway credit.
CREATE TABLE IF NOT EXISTS llm_call (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at    TEXT NOT NULL,
  purpose       TEXT NOT NULL,       -- extract | profile_copy | rationale | ...
  model         TEXT,
  route         TEXT,                -- gateway | direct
  input_tokens  INTEGER,
  output_tokens INTEGER,
  ok            INTEGER DEFAULT 1,
  error         TEXT
);
