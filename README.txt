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


### Gestion des recettes multi-utilisateurs avec partage et recettes publiques
Dans une application de gestion de recettes multi-utilisateurs, on doit gérer :
✔ Les recettes propres à chaque utilisateur
✔ Le partage de recettes entre utilisateurs
✔ Une base de recettes publiques accessibles à tous

1. Associer chaque recette à un utilisateur
    Ajout d’un champ user, visibility et is_default dans le modèle Recipe :
            user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipes")
            visibility = models.CharField(max_length=10, choices=[('private', 'Privée'), ('public', 'Publique')], default='private')
            is_default = models.BooleanField(default=False)  # Recette fournie par l'app (voir section 3)
        ✔ Chaque utilisateur possède ses recettes privées (visibility='private').
        ✔ Il peut choisir de les rendre publiques (visibility='public').
        ✔ Certaines recettes peuvent être des recettes "de base" (is_default=True).
2. Gérer le partage des recettes
    Dans la vue API, permettre aux utilisateurs de voir :
        Leurs propres recettes
        Les recettes publiques des autres utilisateurs
        Les recettes de base fournies par l'application
        Filtrer les recettes en fonction de l’utilisateur connecté :
            ✔ Chaque utilisateur voit uniquement ses recettes privées + celles partagées + les recettes publiques de base.
            ✔ Les recettes publiques restent visibles à tous, mais ne sont modifiables que par leur créateur.
3. Ajouter une base de recettes publiques
Méthode 1 : Utiliser is_default=True (Simple et efficace)
    Créer des recettes de base et marquer is_default=True : user=None, is_default=True et visibility="public"
    ✔ Toutes les recettes avec is_default=True sont accessibles à tous.
    ✔ Elles apparaissent dans get_queryset() sans être liées à un utilisateur.
Méthode 2 : Utiliser un utilisateur "système" (shared_recipes)
    Créer un utilisateur spécial shared_recipes : def get_system_user(): """Retourne l'utilisateur système qui possède les recettes de base"""
    Créer les recettes de base sous cet utilisateur : Recipe.objects.create(user=get_system_user(), recipe_name="Crêpes faciles", description="Recette universelle", visibility="public")
    Adapter get_queryset() : def get_queryset(self):  """Retourne les recettes de l'utilisateur + celles qui sont publiques + les recettes de base"""
                                        user = self.request.user
                                        return Recipe.objects.filter(Q(user=user) | Q(visibility="public") | Q(is_default=True))
    ✔ Les recettes de base sont gérées sous un utilisateur spécifique.
    ✔ Elles peuvent être modifiées par un admin, mais accessibles à tous.
Bonus : Permettre aux utilisateurs de copier une recette publique
    Créer une méthode pour dupliquer une recette : def copy_recipe_to_user(user, recipe)


### Optimisation des traitements dans clean() et save()
Constat actuel :
La plupart des modèles (Recipe, Pan, Ingredient, Store, etc.) appellent self.full_clean() ou self.clean() à chaque save().
Certaines validations métier (unicité, normalisation, etc.) sont faites dans les méthodes du modèle, ce qui garantit l’intégrité même hors API, 
mais peut ralentir les traitements en masse (import, migration, scripts).

Risques :
Ralentissement lors des traitements en masse (imports, bulk, migration de données).
Multiplication des requêtes SQL inutiles si plusieurs validations similaires sont faites sur les mêmes objets.

Best Practices (à appliquer quand tu optimises) :
1. Ne pas appeler full_clean() dans save() systématiquement
- Sauf si on souhaite forcer la validation en dehors de l’API (ex : accès par admin ou script direct).
- Prévoir une option save(validate=True) pour désactiver la validation dans les scripts/bulk.
2. Centraliser la logique métier dans les serializers (API)
- Mettre la plupart des règles métier côté API via DRF serializers.
- Garder dans les modèles uniquement ce qui doit absolument être garanti en toute circonstance (contrainte d’intégrité, unicité…).
3. Optimiser les accès base dans clean()
- Regrouper les requêtes similaires pour éviter plusieurs appels à .filter().exists().
- Ne faire qu’une seule requête, stocker le résultat en variable locale pour tous les checks.
4. Utiliser bulk_create() pour les imports massifs
- Ne déclenche ni save(), ni clean() : à utiliser uniquement si les objets sont déjà validés en amont.
5. Documenter les points d’entrée de validation
- Préciser dans chaque modèle et serializer où se trouve la source de vérité (API ? modèle ?).

À faire plus tard
- Refactoriser les modèles pour retirer les full_clean() inutiles dans save().
- Déplacer la validation métier lourde côté serializers DRF.
- Créer des helpers/commandes d’import massif qui prévalident les données avant un bulk_create.
- Rédiger des tests unitaires couvrant tous les cas de validation côté API.

Nota Bene :
Pour la robustesse, garde les contraintes d’unicité essentielles en base (UniqueConstraint), même si tu les valides aussi côté API.


### UserRecipeAdaptation

Contexte :
Pour permettre aux utilisateurs de personnaliser une recette existante (ex: recette d’un chef ou recette de base), 
nous devons leur offrir la possibilité de créer une **version adaptée**, sans dupliquer intégralement la recette source.

À faire plus tard :
- Créer un modèle `UserRecipeAdaptation` lié à `User` et `Recipe`
- Stocker les adaptations spécifiques : `custom_pan`, `custom_servings`, `custom_title`, `custom_trick`, etc.
- Conserver un lien vers la recette d’origine pour traçabilité
- Offrir à l’utilisateur une interface pour retrouver ses adaptations, les partager, ou les recalculer automatiquement
- Ne pas confondre adaptation = transformation contextuelle ≠ nouvelle recette indépendante

Objectif :
Ne jamais dupliquer inutilement les recettes en base mais permettre un système fluide d’adaptation personnalisée (à la manière de “forks” intelligents).

### Ajout des allergènes dans une recette. Penser à la structure de données pour ça.

### Ajout module IA, agent AI, MCP