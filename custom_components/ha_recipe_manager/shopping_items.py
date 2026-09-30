"""Parse and combine ingredient quantities without guessing incompatible amounts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import re
import unicodedata

from .models import Ingredient, clean_text

# Keep matching explicit: e.g. red onions and spring onions stay separate.
_NAME_ALIASES = {
    "karotten": "karotte",
    "möhre": "karotte",
    "möhren": "karotte",
    "zwiebeln": "zwiebel",
    "kartoffeln": "kartoffel",
    "tomaten": "tomate",
    "eier": "ei",
    "zitronen": "zitrone",
}
_UNITS: dict[str, tuple[str, Decimal, str]] = {}
for _dimension, _factor, _symbol, _aliases in (
    ("mass", "1", "g", ("g", "gramm", "grams", "gram")),
    ("mass", "1000", "kg", ("kg", "kilogramm", "kilo")),
    ("mass", "0.001", "mg", ("mg", "milligramm")),
    ("mass", "10", "dag", ("dag", "dkg", "dekagramm")),
    ("volume", "1", "ml", ("ml", "milliliter")),
    ("volume", "10", "cl", ("cl", "zentiliter")),
    ("volume", "100", "dl", ("dl", "deziliter")),
    ("volume", "1000", "l", ("l", "liter", "litre")),
    ("count", "1", "", ("", "x", "×", "stk", "stück", "stücke", "stueck")),
    ("dose", "1", "Dose", ("dose", "dosen")),
    ("packung", "1", "Packung", ("packung", "packungen", "pkg")),
    ("bund", "1", "Bund", ("bund", "bünde")),
    ("zehe", "1", "Zehe", ("zehe", "zehen")),
    ("el", "1", "EL", ("el", "esslöffel", "essloeffel")),
    ("tl", "1", "TL", ("tl", "teelöffel", "teeloeffel")),
):
    for _alias in _aliases:
        _UNITS[_alias] = (_dimension, Decimal(_factor), _symbol)

_NUMBER = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?|[½¼¾⅓⅔⅛⅜⅝⅞])"
_PREFIX = re.compile(rf"^({_NUMBER})\s*(.*)$")
_FRACTIONS = {
    "½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
}


def _text_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _unit_key(value: str) -> str:
    return _text_key(value).rstrip(".")


def _quantity(value: str) -> Decimal | None:
    value = _FRACTIONS.get(value, value).replace(",", ".")
    try:
        if "/" in value:
            whole, _, fraction = value.rpartition(" ")
            numerator, denominator = fraction.split("/")
            amount = Decimal(whole or "0") + Decimal(numerator) / Decimal(denominator)
        else:
            amount = Decimal(value)
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None
    return amount if amount.is_finite() and amount > 0 else None


def _format_quantity(amount: Decimal) -> str:
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


@dataclass(frozen=True)
class ShoppingIngredient:
    """One amount, stored in the base unit of its dimension."""

    name: str
    note: str
    amount: Decimal
    dimension: str
    factor: Decimal
    unit: str

    @property
    def key(self) -> tuple[str, str, str]:
        name = _text_key(self.name)
        return (_NAME_ALIASES.get(name, name), _text_key(self.note), self.dimension)

    def add(self, other: ShoppingIngredient) -> ShoppingIngredient:
        """Combine compatible quantities, preserving the existing display name/unit."""
        return replace(self, amount=self.amount + other.amount)

    def label(self) -> str:
        quantity = _format_quantity(self.amount / self.factor)
        prefix = f"{quantity}x" if self.dimension == "count" else f"{quantity} {self.unit}"
        label = f"{prefix} {self.name}"
        return f"{label} ({self.note})" if self.note else label


def shopping_ingredient(ingredient: Ingredient) -> ShoppingIngredient | None:
    """Read a structured recipe ingredient; leave ambiguous quantities untouched."""
    quantity = clean_text(ingredient.get("quantity"))
    unit = clean_text(ingredient.get("unit"))
    if not quantity:
        amount = Decimal(1) if not unit else None
    else:
        amount = _quantity(quantity)
    if amount is None:
        return None
    unit_key = _unit_key(unit)
    dimension, factor, symbol = _UNITS.get(unit_key, (f"unit:{unit_key}", Decimal(1), unit))
    return ShoppingIngredient(
        clean_text(ingredient.get("name")), clean_text(ingredient.get("note")),
        amount * factor, dimension, factor, symbol,
    )


def parse_shopping_label(label: str, recipe_unit: str = "") -> ShoppingIngredient | None:
    """Read list entries such as '200g Karotten', '2x Zwiebel' or 'Sellerie'."""
    label = clean_text(label)
    note = ""
    if note_match := re.search(r"\s+\(([^()]*)\)$", label):
        note = note_match[1].strip()
        label = label[:note_match.start()].strip()
    quantity = ""
    unit = ""
    if match := _PREFIX.fullmatch(label):
        quantity, label = match.groups()
        if re.match(r"^[x×](?:\s|$)", label, re.IGNORECASE):
            label = label[1:].strip()
        else:
            first, separator, remainder = label.partition(" ")
            if separator and (_unit_key(first) in _UNITS or
                              (recipe_unit and _unit_key(first) == _unit_key(recipe_unit))):
                unit, label = first, remainder.strip()
            elif not label or not match[0][len(match[1]):].startswith(" "):
                # Do not reinterpret unrecognised attached units as counted names.
                return None
    if not label:
        return None
    return shopping_ingredient({"name": label, "note": note, "quantity": quantity, "unit": unit})
