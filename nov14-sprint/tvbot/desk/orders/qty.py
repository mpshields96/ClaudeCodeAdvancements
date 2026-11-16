"""Exact share quantities for the desk (stdlib only).

A quantity is either a positive ``int`` (whole shares, exactly what the desk has always used) or a
positive exact ``Decimal`` with at most MAX_DP decimal places (fractional shares). ``parse`` is the
only way in. Integral values always come back as ``int`` so whole-share paths are unchanged.

Floats are never used for quantity arithmetic. A float input is read through ``repr`` (the shortest
round-trip text), so 0.1 means 0.1, not 0.1000000000000000055.
"""
from decimal import Decimal, InvalidOperation

MAX_DP = 9            # Alpaca: "The qty field supports up to 9 decimal places"; the desk refuses more
MAX_DIGITS = 15       # keeps every fractional value exactly representable as a JSON float


class QtyError(ValueError):
    pass


def _to_dec(v):
    if isinstance(v, bool) or v is None:
        raise QtyError("quantity must be a number, got %r" % (v,))
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, Decimal):
        return v
    if isinstance(v, float):
        return Decimal(repr(v))
    if isinstance(v, str):
        s = v.strip()
        if not s:
            raise QtyError("quantity is empty")
        try:
            return Decimal(s)
        except InvalidOperation:
            raise QtyError("quantity %r is not a number" % (v,))
    raise QtyError("quantity must be a number, got %s" % type(v).__name__)


def parse(v, allow_zero=False):
    """Return an int (integral) or an exact Decimal (fractional). Raise QtyError otherwise."""
    d = _to_dec(v)
    if not d.is_finite():
        raise QtyError("quantity must be finite")
    if d < 0 or (d == 0 and not allow_zero):
        raise QtyError("quantity must be greater than zero")
    if d == d.to_integral_value():
        return int(d)
    # normalize() obeys Decimal's active precision and can round away an invalid tail.
    sign, digits, exp = d.as_tuple()
    while digits[-1] == 0:
        digits, exp = digits[:-1], exp + 1
    n = Decimal((sign, digits, exp))
    exp = n.as_tuple().exponent
    if -exp > MAX_DP:
        raise QtyError("quantity has more than %d decimal places" % MAX_DP)
    if len(n.as_tuple().digits) > MAX_DIGITS:
        raise QtyError("quantity has more than %d significant digits" % MAX_DIGITS)
    return n


def parse_signed(v):
    """Like parse, for a signed position quantity (zero allowed)."""
    d = _to_dec(v)
    if not d.is_finite():
        raise QtyError("quantity must be finite")
    q = parse(d.copy_abs(), allow_zero=True)
    return -q if d < 0 else q


def is_fractional(q):
    return isinstance(q, Decimal) and q != q.to_integral_value()


def dec(q):
    """Exact Decimal of a quantity (int, Decimal, a float read through repr, or a decimal string)."""
    if isinstance(q, Decimal):
        return q
    if isinstance(q, int) and not isinstance(q, bool):
        return Decimal(q)
    return _to_dec(q)


def norm(d):
    """Normalize the result of exact arithmetic back to int-or-Decimal (zero allowed, sign kept)."""
    d = dec(d)
    if d == d.to_integral_value():
        return int(d)
    return d.normalize()


def text(q):
    """Broker/ids/phrase rendering: '3' for ints, '0.25' for fractions, never exponent form."""
    if isinstance(q, bool):
        raise QtyError("quantity must be a number")
    if isinstance(q, int):
        return str(q)
    q = norm(q)
    if isinstance(q, int):
        return str(q)
    return format(q, "f")


def to_json(q):
    """JSON value: int stays int; a fraction becomes a float (exact within MAX_DP/MAX_DIGITS)."""
    q = norm(q)
    return q if isinstance(q, int) else float(q)


def json_default(o):
    """json.dumps default= hook that writes Decimal quantities exactly."""
    if isinstance(o, Decimal):
        return to_json(o)
    raise TypeError("%r is not JSON serializable" % (o,))


def json_default_str(o):
    """For sites that used default=str: Decimal goes through to_json, anything else through str."""
    if isinstance(o, Decimal):
        return to_json(o)
    return str(o)
