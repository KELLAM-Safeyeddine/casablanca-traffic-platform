"""Calcul du contraste WCAG pour les couleurs sRGB opaques des thèmes."""


def luminance(color: str) -> float:
    """Convertir une couleur #RRGGBB en luminance relative WCAG."""
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError("Expected an opaque #RRGGBB color")
    channels = [int(color[start : start + 2], 16) / 255 for start in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return sum(
        weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """Retourner un rapport de 1 à 21 : (Lclair + 0,05)/(Lsombre + 0,05)."""
    values = sorted((luminance(foreground), luminance(background)))
    return (values[1] + 0.05) / (values[0] + 0.05)
