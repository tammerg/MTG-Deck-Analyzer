/**
 * Deck card category utilities.
 *
 * Categories come from the deck builder engine (e.g., 'ramp', 'draw', 'removal').
 */

const CATEGORY_DISPLAY_NAMES: Record<string, string> = {
  commander: 'Commander',
  companion: 'Companion',
  ramp: 'Ramp',
  draw: 'Card Draw',
  removal: 'Removal',
  boardwipe: 'Board Wipe',
  counterspell: 'Counterspell',
  tutor: 'Tutor',
  win_condition: 'Win Condition',
  combo_piece: 'Combo Piece',
  protection: 'Protection',
  recursion: 'Recursion',
  graveyard: 'Graveyard',
  utility: 'Utility',
  threat: 'Threat',
  land: 'Land',
  basic_land: 'Basic Land',
  nonbasic_land: 'Nonbasic Land',
  artifact: 'Artifact',
  enchantment: 'Enchantment',
  planeswalker: 'Planeswalker',
  creature: 'Creature',
  staple: 'Staple',
  filler: 'Filler',
};

/**
 * Get a human-readable display name for a card category.
 *
 * Usage:
 *   getCategoryDisplayName('win_condition') → 'Win Condition'
 *   getCategoryDisplayName('unknown')       → 'Unknown'
 */
export function getCategoryDisplayName(category: string): string {
  if (!category) return 'Unknown';
  return CATEGORY_DISPLAY_NAMES[category.toLowerCase()] ?? capitalize(category.replace(/_/g, ' '));
}

/**
 * Get a Tailwind CSS color class for a category badge.
 *
 * Usage:
 *   getCategoryColor('ramp') → 'bg-green-800 text-green-200'
 */
export function getCategoryColor(category: string): string {
  const colorMap: Record<string, string> = {
    commander: 'bg-yellow-700 text-yellow-100',
    companion: 'bg-yellow-600 text-yellow-100',
    ramp: 'bg-green-800 text-green-200',
    draw: 'bg-blue-800 text-blue-200',
    removal: 'bg-red-800 text-red-200',
    boardwipe: 'bg-red-900 text-red-200',
    counterspell: 'bg-blue-900 text-blue-200',
    tutor: 'bg-purple-800 text-purple-200',
    win_condition: 'bg-orange-800 text-orange-200',
    combo_piece: 'bg-orange-900 text-orange-200',
    protection: 'bg-cyan-800 text-cyan-200',
    recursion: 'bg-violet-800 text-violet-200',
    graveyard: 'bg-stone-700 text-stone-200',
    utility: 'bg-slate-700 text-slate-200',
    threat: 'bg-rose-800 text-rose-200',
    land: 'bg-amber-900 text-amber-200',
    basic_land: 'bg-amber-800 text-amber-200',
    nonbasic_land: 'bg-amber-900 text-amber-200',
    staple: 'bg-indigo-800 text-indigo-200',
    filler: 'bg-slate-800 text-slate-300',
  };
  return colorMap[category.toLowerCase()] ?? 'bg-slate-700 text-slate-300';
}

/**
 * Get the sort order for deck categories (commander first, lands last).
 */
export function getCategorySortOrder(category: string): number {
  const order: Record<string, number> = {
    commander: 0,
    companion: 1,
    win_condition: 2,
    combo_piece: 3,
    ramp: 4,
    draw: 5,
    removal: 6,
    counterspell: 7,
    boardwipe: 8,
    tutor: 9,
    protection: 10,
    threat: 11,
    recursion: 12,
    utility: 13,
    staple: 14,
    filler: 15,
    land: 16,
    nonbasic_land: 17,
    basic_land: 18,
  };
  return order[category.toLowerCase()] ?? 99;
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
