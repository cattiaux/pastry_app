### doc métier des IngredientPrice :
- Règle stricte sur l’association des magasins (Store) :
    - Un IngredientPrice doit être lié à un Store existant.
    - L’API refuse la création d’un prix si le Store n’existe pas (400 Bad Request).
    - Le frontend doit gérer cette contrainte en proposant la création du Store en amont.
    - Une future évolution pourrait ajouter une API spécifique permettant de créer Store + Prix en une seule requête.

Dette Technique à Prévoir : 

### Gestion de l’unicité sur `category_name`
- En développement, l’unicité est gérée par l’API dans `serializers.py`. Pour éviter des conflits le champ `category_name` n'a pas encore `unique=True`.
- En production, ajouter `unique=True` sur `category_name` dans `models.py` pour garantir l’unicité des catégories en base.
- Ne pas oublier d’exécuter `makemigrations` et `migrate` lors du passage en production.

### Gestion de l’unicité sur `label_name`
- En développement, l’unicité est gérée par l’API dans `serializers.py`. Pour éviter des conflits le champ `label_name` n'a pas encore `unique=True`.
- En production, ajouter `unique=True` sur `label_name` dans `models.py` pour garantir l’unicité des catégories en base.
- Ne pas oublier d’exécuter `makemigrations` et `migrate` lors du passage en production.

### Gestion de l’unicité sur `ingredient_name`
- En développement, l’unicité est gérée par l’API dans `serializers.py`. Pour éviter des conflits le champ `ingredient_name` n'a pas encore `unique=True`.
- En production, ajouter `unique=True` sur `ingredient_name` dans `models.py` pour garantir l’unicité des catégories en base.
- Ne pas oublier d’exécuter `makemigrations` et `migrate` lors du passage en production.

### Mapping entre Noms de Modèles (Singulier) et URLs (Pluriel)
- Problème actuel :
Actuellement, dans nos tests et nos méthodes génériques (create_related_models_api notamment), 
nous utilisons les noms des modèles en version plurielle pour construire les URLs d’API.
or, certains noms de modèles ne suivent pas une simple règle d’ajout d’un "s" (ex: category → categories).

- Amélioration future (déjà existant dans pastry_app/utils.py mais pas encore utilisé) :  
Créer un dictionnaire de mapping global pour assurer la conversion correcte entre :
    - Le nom du modèle en base de données (ex: "category")
    - Le nom utilisé dans l’URL d’API (ex: "categories")

- Avantages :
Plus de robustesse dans create_related_models_api et autres méthodes
Évite d’écrire manuellement des noms pluriels dans les tests
Facilite les futures évolutions si d’autres conventions d’URL sont adoptées

- Exemple d'utilisation : 
related_url = base_url(get_api_url_name(related_model_name))