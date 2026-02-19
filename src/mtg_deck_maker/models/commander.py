"""Commander data model supporting solo, partner, background, and companion configurations."""

from __future__ import annotations

from dataclasses import dataclass, field

from mtg_deck_maker.models.card import Card


class CommanderValidationError(Exception):
    """Raised when a commander configuration is invalid."""


@dataclass(slots=True)
class Commander:
    """Commander configuration supporting all valid commander arrangements.

    Supports:
    - Solo commander (just primary)
    - Partner pair (primary + partner, both have "Partner" keyword)
    - Choose a Background (primary has "Choose a Background", background is a Background enchantment)
    - Companion (any of the above + a companion creature)
    """

    primary: Card
    partner: Card | None = None
    background: Card | None = None
    companion: Card | None = None

    def combined_color_identity(self) -> list[str]:
        """Compute the union color identity of all commander components.

        The color identity of a commander deck is the union of the color
        identities of all commanders (primary, partner, background).
        Companions do not affect the deck's color identity but must be
        within it.

        Returns:
            Sorted list of color characters (e.g., ["B", "G", "U", "W"]).
        """
        wubrg_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        identity: set[str] = set()

        identity.update(self.primary.color_identity)

        if self.partner is not None:
            identity.update(self.partner.color_identity)

        if self.background is not None:
            identity.update(self.background.color_identity)

        return sorted(identity, key=lambda c: wubrg_order.get(c, 99))

    def deck_size(self) -> int:
        """Return the number of non-commander cards needed in the deck.

        - Solo commander: 99 cards (100 - 1 commander)
        - Partner pair: 98 cards (100 - 2 commanders)
        - Background: 98 cards (100 - commander - background)
        - Companion occupies one of the non-commander slots
        """
        commander_count = 1
        if self.partner is not None:
            commander_count = 2
        if self.background is not None:
            commander_count = 2
        return 100 - commander_count

    def total_deck_size(self) -> int:
        """Return the total deck size (always 100 for Commander)."""
        return 100

    def validate(self) -> list[str]:
        """Validate the commander configuration.

        Returns:
            List of validation error messages. Empty list means valid.
        """
        errors: list[str] = []

        # Primary must be commander-legal
        if not self.primary.legal_commander:
            errors.append(
                f"{self.primary.name!r} is not legal as a commander."
            )

        # Check primary is a legendary creature or has specific abilities
        if "Legendary" not in self.primary.type_line:
            errors.append(
                f"{self.primary.name!r} is not a legendary card."
            )

        # Partner validation
        if self.partner is not None:
            if not self.partner.legal_commander:
                errors.append(
                    f"Partner {self.partner.name!r} is not legal as a commander."
                )

            primary_has_partner = "Partner" in self.primary.keywords
            partner_has_partner = "Partner" in self.partner.keywords

            # Check for "Partner with" - specific partner pairings
            primary_has_partner_with = any(
                kw.startswith("Partner with") for kw in self.primary.keywords
            )
            partner_has_partner_with = any(
                kw.startswith("Partner with") for kw in self.partner.keywords
            )

            if primary_has_partner_with or partner_has_partner_with:
                # Specific partner pairing - both must reference each other
                # For now, just check both have some form of partner keyword
                if not (primary_has_partner or primary_has_partner_with):
                    errors.append(
                        f"{self.primary.name!r} does not have the Partner keyword."
                    )
                if not (partner_has_partner or partner_has_partner_with):
                    errors.append(
                        f"{self.partner.name!r} does not have the Partner keyword."
                    )
            else:
                # Generic partner - both need "Partner"
                if not primary_has_partner:
                    errors.append(
                        f"{self.primary.name!r} does not have the Partner keyword."
                    )
                if not partner_has_partner:
                    errors.append(
                        f"{self.partner.name!r} does not have the Partner keyword."
                    )

        # Background validation
        if self.background is not None:
            primary_has_choose_bg = (
                "Choose a Background" in self.primary.keywords
            )
            if not primary_has_choose_bg:
                errors.append(
                    f"{self.primary.name!r} does not have 'Choose a Background'."
                )

            bg_is_background = "Background" in self.background.type_line
            if not bg_is_background:
                errors.append(
                    f"{self.background.name!r} is not a Background enchantment."
                )

        # Cannot have both partner and background
        if self.partner is not None and self.background is not None:
            errors.append(
                "Cannot have both a partner and a background."
            )

        # Companion validation
        if self.companion is not None:
            companion_has_keyword = "Companion" in self.companion.keywords
            if not companion_has_keyword:
                errors.append(
                    f"{self.companion.name!r} does not have the Companion keyword."
                )

            # Companion must be within the deck's color identity
            deck_identity = set(self.combined_color_identity())
            companion_identity = set(self.companion.color_identity)
            if not companion_identity.issubset(deck_identity):
                extra = companion_identity - deck_identity
                errors.append(
                    f"Companion {self.companion.name!r} has colors "
                    f"{extra} outside the commander's color identity."
                )

        return errors

    def all_commander_cards(self) -> list[Card]:
        """Return all cards that occupy commander zone slots."""
        cards = [self.primary]
        if self.partner is not None:
            cards.append(self.partner)
        if self.background is not None:
            cards.append(self.background)
        return cards
