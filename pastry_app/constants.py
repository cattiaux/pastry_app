UNIT_CHOICES = [
    ('g', 'Grams'),
    ('kg', 'Kilograms'),
    ('ml', 'Milliliters'),
    ('cl', 'Centiliters'),
    ('l', 'Liters'),
    ('tsp', 'Teaspoons'),
    ('tbsp', 'Tablespoons'),
    ('cas', 'Cuillère à soupe'),
    ('cc', 'Cuillère à café'),
    ('cup', 'Cups'),
    ('unit', 'Unit'),
    # Add more units as needed
]

# Liste des catégories disponibles (pour recette et/ou ingrédient) et leur type associé.
# Format : 
#   - clé interne : Utilisée pour les bases de données ou les API. Normalement en minuscule sans espace pour éviter les erreurs.
#   - nom affiché : Utilisée pour l’affichage utilisateur (ex: dans Django Admin). Peut contenir des majuscules et des accents
#   - type de catégorie : Permet de classifier chaque catégorie selon son usage.
CATEGORY_DEFINITIONS = [
    ("desserts", "Desserts", "recipe"),
    ("plats", "Plats", "recipe"),
    ("entrees", "Entrées", "recipe"),
    ("boissons", "Boissons", "recipe"),
    ("snacks", "Snacks", "recipe"),
    ("vegan", "Vegan", "both"),
    ("sans gluten", "Sans Gluten", "both"),
    ("farines", "Farines", "ingredient"),
    ("fruits", "Fruits", "ingredient"),
    ("epices", "Épices", "ingredient"),
    ('cakes', 'Gâteaux', 'recipe'),
    ('tarts', 'Tartes', 'recipe'),
    ('entremets', 'Entremets', 'recipe'),
    ('flans', 'Flans', 'recipe'),
    ('bread', 'Pains', 'recipe'),
    ('viennoiseries', 'Viennoiseries', 'recipe'),
    ('biscuits', 'Biscuits', 'recipe'),
    ('cremeux', 'Crémeux', 'recipe'),
    ('confits', 'Confits/Coulis', 'recipe'),
    ('ganaches', 'Ganaches', 'recipe'),
    ('mousses', 'Mousses/Ganaches montées', 'recipe'),
    ('pther', 'Autre', 'both'),
    # Add more units as needed
]

# Convertit toutes les clés internes en minuscule
CATEGORY_DEFINITIONS = [(key.lower(), label, c_type) for key, label, c_type in CATEGORY_DEFINITIONS]
# Dictionnaire qui associe `category_name` à `category_type`
CATEGORY_TYPE_MAP = {key: c_type for key, _, c_type in CATEGORY_DEFINITIONS}
# Liste des noms de catégories pour la validation
CATEGORY_NAME_CHOICES = list(CATEGORY_TYPE_MAP.keys())

# Liste des labels disponibles (pour recette et/ou ingrédient) et leur type associé.
# Format : 
#   - clé interne : Utilisée pour les bases de données ou les API. Normalement en minuscule (de préférence sans espace) pour éviter les erreurs.
#   - nom affiché : Utilisée pour l’affichage utilisateur (ex: dans Django Admin). Peut contenir des majuscules et des accents
#   - type de label : Permet de classifier chaque label selon son usage.
LABEL_DEFINITIONS = [
    ("vegan", "Vegan", "recipe"),
    ("sans gluten", "Sans Gluten", "both"),
    ("bio", "Bio/Organique", "ingredient"),
    ("label rouge", "Label Rouge", "ingredient"),
    ('other', 'Autre', 'both'),
    # Add more units as needed
]

# Convertit toutes les clés internes en minuscule
LABEL_DEFINITIONS = [(key.lower(), label, c_type) for key, label, c_type in LABEL_DEFINITIONS]
# Dictionnaire qui associe `category_name` à `category_type`
LABEL_TYPE_MAP = {key: c_type for key, _, c_type in LABEL_DEFINITIONS}
# Liste des noms de catégories pour la validation
LABEL_NAME_CHOICES = list(LABEL_TYPE_MAP.keys())