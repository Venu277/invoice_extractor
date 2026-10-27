from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def round_half_up(val: Union[Decimal, int, str], places: int = 2) -> Decimal:
    """Rounds Decimal using ROUND_HALF_UP (standard accounting line level)."""
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    target = Decimal("10") ** -places
    return val.quantize(target, rounding=ROUND_HALF_UP)


def rupees_to_paise(amount: Union[Decimal, int, str, float]) -> int:
    """Converts a rupee amount (Decimal/str/int) to integer paise, rounding half-up."""
    if amount is None:
        return 0
    if isinstance(amount, float):
        # Convert float via string representation to avoid precision corruption
        d = Decimal(str(amount))
    elif isinstance(amount, Decimal):
        d = amount
    else:
        d = Decimal(str(amount).replace(",", "").strip())
    paise_dec = (d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(paise_dec)


def paise_to_decimal(paise: Union[int, None]) -> Decimal:
    """Converts integer paise to Decimal rupees."""
    if paise is None:
        return Decimal("0.00")
    return (Decimal(paise) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_inr(amount_paise: Union[int, Decimal, None], include_symbol: bool = True) -> str:
    """
    Formats integer paise or Decimal rupees in Indian numbering format:
    e.g. 12345600 paise -> 'Rs. 1,23,456.00'
    """
    if amount_paise is None:
        amount_paise = 0

    if isinstance(amount_paise, int):
        d = paise_to_decimal(amount_paise)
    elif isinstance(amount_paise, Decimal):
        d = round_half_up(amount_paise, 2)
    else:
        d = Decimal(str(amount_paise))

    is_negative = d < 0
    abs_d = abs(d)

    # Format to 2 decimal places
    s = f"{abs_d:.2f}"
    parts = s.split(".")
    int_part, frac_part = parts[0], parts[1]

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        # Group rest by 2 digits from right to left
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last3

    res = f"{formatted_int}.{frac_part}"
    prefix = "Rs. " if include_symbol else ""
    if is_negative:
        return f"-{prefix}{res}"
    return f"{prefix}{res}"
