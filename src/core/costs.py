def effective_spread(quoted_spread: float, tick_floor: float) -> float:
    return max(quoted_spread, tick_floor)


def slip_model(quoted_spread: float, side: str, tick_floor: float) -> float:
    # Simple half-spread model
    return effective_spread(quoted_spread, tick_floor) / 2.0
