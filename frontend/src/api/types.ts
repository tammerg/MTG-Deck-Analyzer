// TypeScript types matching backend Pydantic schemas

export interface CardResponse {
  id: number;
  oracle_id: string;
  name: string;
  type_line: string;
  oracle_text: string;
  mana_cost: string;
  cmc: number;
  colors: string[];
  color_identity: string[];
  keywords: string[];
  edhrec_rank: number | null;
  legal_commander: boolean;
  legal_brawl: boolean;
  updated_at: string;
  image_url: string | null;
}

export interface PrintingResponse {
  id: number;
  scryfall_id: string;
  card_id: number;
  set_code: string;
  collector_number: string;
  lang: string;
  rarity: string;
  finishes: string[];
  released_at: string;
  is_promo: boolean;
  is_reprint: boolean;
  image_url: string;
}

export interface DeckCardResponse {
  card_id: number;
  quantity: number;
  category: string;
  is_commander: boolean;
  card_name: string;
  cmc: number;
  colors: string[];
  price: number;
  mana_cost: string;
  type_line: string;
  oracle_text: string;
  image_url: string | null;
}

export interface DeckResponse {
  id: number | null;
  name: string;
  format: string;
  budget_target: number | null;
  created_at: string;
  cards: DeckCardResponse[];
  total_cards: number;
  total_price: number;
  average_cmc: number;
  color_distribution: Record<string, number>;
  commanders: DeckCardResponse[];
}

export interface DeckBuildRequest {
  commander: string;
  partner?: string;
  budget: number;
  seed?: number;
  smart?: boolean;
  provider?: string;
}

export type DeckExportFormat = 'csv' | 'moxfield' | 'archidekt';

export interface DeckExportRequest {
  format: DeckExportFormat;
}

export interface DeckExportResponse {
  content: string;
  format: DeckExportFormat;
  deck_id: number;
}

export interface ResearchRequest {
  commander: string;
  budget?: number;
  provider?: string;
}

export interface ResearchResponse {
  commander_name: string;
  strategy_overview: string;
  key_cards: string[];
  budget_staples: string[];
  combos: string[];
  win_conditions: string[];
  cards_to_avoid: string[];
  parse_success: boolean;
}

export interface HealthResponse {
  status: string;
  db_exists: boolean;
  card_count: number;
}

// Config types matching backend's nested config schema
export interface ConstraintsConfig {
  avoid_reserved_list: boolean;
  avoid_infinite_combos: boolean;
  max_price_per_card: number;
  allow_tutors: boolean;
  allow_fast_mana: boolean;
  include_staples: boolean;
  prefer_nonfoil: boolean;
  exclude_cards: string[];
  force_cards: string[];
}

export interface PricingConfig {
  preferred_source: string;
  preferred_currency: string;
  preferred_finish: string;
  price_policy: string;
}

export interface GeneralConfig {
  data_dir: string;
  cache_ttl_hours: number;
  offline_mode: boolean;
}

export interface LLMConfig {
  provider: string;
  openai_model: string;
  anthropic_model: string;
  max_tokens: number;
  temperature: number;
  timeout_s: number;
  max_retries: number;
  research_enabled: boolean;
  priority_bonus: number;
}

export interface AppConfig {
  constraints: ConstraintsConfig;
  pricing: PricingConfig;
  general: GeneralConfig;
  llm: LLMConfig;
}

export interface AppConfigUpdate {
  constraints?: Partial<ConstraintsConfig>;
  pricing?: Partial<PricingConfig>;
  general?: Partial<GeneralConfig>;
  llm?: Partial<LLMConfig>;
}

export interface CardSearchParams {
  q?: string;
  color?: string;
  type?: string;
  limit?: number;
  offset?: number;
}

export interface CardSearchResponse {
  results: CardResponse[];
  total: number;
}

export interface DeckListItem {
  id: number;
  name: string;
  format: string;
  budget_target: number | null;
  created_at: string;
  total_cards: number;
  total_price: number;
}

export interface AdviseRequest {
  question: string;
  provider?: string;
}

export interface DeckAdviseResponse {
  advice: string;
}
