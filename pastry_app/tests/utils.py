def normalize_case(value):
    """ Applique la même normalisation (lowercase) que dans les modèles"""
    return value.lower() if value else value
