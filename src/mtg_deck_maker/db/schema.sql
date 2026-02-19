-- MTG Deck Maker Database Schema
-- Version 1

-- Cards are oracle-level entities (unique rules text)
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY,
  oracle_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  type_line TEXT,
  oracle_text TEXT,
  mana_cost TEXT,
  cmc REAL,
  colors TEXT,
  color_identity TEXT,
  keywords TEXT,
  edhrec_rank INTEGER,
  legal_commander INTEGER DEFAULT 0,
  legal_brawl INTEGER DEFAULT 0,
  updated_at TEXT
);

-- Printings are set-level entities (unique physical print)
CREATE TABLE IF NOT EXISTS printings (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL REFERENCES cards(id),
  scryfall_id TEXT UNIQUE NOT NULL,
  set_code TEXT NOT NULL,
  collector_number TEXT NOT NULL,
  lang TEXT DEFAULT 'en',
  rarity TEXT,
  finishes TEXT,
  tcgplayer_id INTEGER,
  cardmarket_id INTEGER,
  released_at TEXT,
  is_promo INTEGER DEFAULT 0,
  is_reprint INTEGER DEFAULT 0,
  UNIQUE(card_id, set_code, collector_number, lang)
);

-- Faces for MDFCs and split cards
CREATE TABLE IF NOT EXISTS card_faces (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL REFERENCES cards(id),
  face_index INTEGER NOT NULL,
  face_name TEXT,
  mana_cost TEXT,
  type_line TEXT,
  oracle_text TEXT,
  colors TEXT
);

-- Pricing per printing, per finish, per source
CREATE TABLE IF NOT EXISTS prices (
  id INTEGER PRIMARY KEY,
  printing_id INTEGER NOT NULL REFERENCES printings(id),
  source TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  price REAL,
  finish TEXT DEFAULT 'nonfoil',
  retrieved_at TEXT NOT NULL
);

-- Card categorization tags with confidence
CREATE TABLE IF NOT EXISTS card_tags (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL REFERENCES cards(id),
  tag TEXT NOT NULL,
  confidence REAL DEFAULT 1.0,
  UNIQUE(card_id, tag)
);

-- Commander pair relationships (partner, background, companion)
CREATE TABLE IF NOT EXISTS commander_pairs (
  id INTEGER PRIMARY KEY,
  partner_a INTEGER NOT NULL REFERENCES cards(id),
  partner_b INTEGER REFERENCES cards(id),
  background INTEGER REFERENCES cards(id),
  companion INTEGER REFERENCES cards(id)
);

-- Persisted decklists
CREATE TABLE IF NOT EXISTS decks (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  format TEXT DEFAULT 'commander',
  budget_target REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deck_cards (
  id INTEGER PRIMARY KEY,
  deck_id INTEGER NOT NULL REFERENCES decks(id),
  card_id INTEGER NOT NULL REFERENCES cards(id),
  quantity INTEGER DEFAULT 1,
  category TEXT,
  is_commander INTEGER DEFAULT 0,
  is_companion INTEGER DEFAULT 0
);

-- ID mappings for cross-API resolution
CREATE TABLE IF NOT EXISTS id_mappings (
  id INTEGER PRIMARY KEY,
  oracle_id TEXT NOT NULL,
  scryfall_id TEXT,
  tcgplayer_id INTEGER,
  cardmarket_id INTEGER,
  UNIQUE(oracle_id, scryfall_id)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
CREATE INDEX IF NOT EXISTS idx_cards_color_identity ON cards(color_identity);
CREATE INDEX IF NOT EXISTS idx_cards_legal_commander ON cards(legal_commander);
CREATE INDEX IF NOT EXISTS idx_printings_card_id ON printings(card_id);
CREATE INDEX IF NOT EXISTS idx_printings_tcgplayer_id ON printings(tcgplayer_id);
CREATE INDEX IF NOT EXISTS idx_prices_printing_id ON prices(printing_id);
CREATE INDEX IF NOT EXISTS idx_prices_retrieved_at ON prices(retrieved_at);
CREATE INDEX IF NOT EXISTS idx_card_tags_card_id ON card_tags(card_id);
CREATE INDEX IF NOT EXISTS idx_card_tags_tag ON card_tags(tag);
