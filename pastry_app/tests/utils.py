def normalize_case(value):
    """ Applique la même normalisation (lowercase) que dans les modèles"""
    return " ".join(value.lower().strip().split()) if value else value
