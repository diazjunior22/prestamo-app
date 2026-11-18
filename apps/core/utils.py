from decimal import Decimal, ROUND_HALF_UP

def format_cop(amount, show_cents=False) -> str:
    """
    Formats a numeric/Decimal value as Colombian Pesos (COP).
    Example: 1500000 -> "$ 1.500.000 COP"
    """
    if amount is None:
        return "$ 0 COP"
    
    try:
        val = Decimal(str(amount))
    except Exception:
        return "$ 0 COP"

    if show_cents:
        # Round to 2 decimals
        val = val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        int_part = int(val)
        dec_part = int(abs(val - int_part) * 100)
        formatted_int = f"{int_part:,}".replace(",", ".")
        return f"$ {formatted_int},{dec_part:02d} COP"
    else:
        # Standard integer representation for COP display
        rounded_int = int(val.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        formatted = f"{rounded_int:,}".replace(",", ".")
        return f"$ {formatted} COP"

def quantize_currency(amount) -> Decimal:
    """
    Ensures precise 2-decimal representation with ROUND_HALF_UP.
    Guarantees no floating-point inaccuracies.
    """
    if amount is None:
        return Decimal('0.00')
    if isinstance(amount, float):
        amount = str(amount)
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

