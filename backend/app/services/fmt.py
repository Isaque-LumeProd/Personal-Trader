def br(value: float, digits: int = 2) -> str:
    """Formata número no padrão brasileiro (1.234,56)."""
    s = f"{value:,.{digits}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")
