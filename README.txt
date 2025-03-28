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

### Sécurisation des Paramètres Sensibles dans settings.py
Problème : Actuellement, des informations sensibles sont en dur dans settings.py​.
Impact : Cela pose un risque en cas de fuite du code source ou de partage du repository.
Solution : Utiliser des Variables d'Environnement
    - Etape 1 : installation : pip install python-dotenv
    - Etape 2 : code dans settings.py :
import os
from dotenv import load_dotenv
# Charger les variables d'environnement depuis un fichier .env
load_dotenv()
# Clé secrète Django
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'fallback-secret-key')
# Mode Debug (par défaut False en production)
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
# Configuration de la base de données
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'pastry_app'),
        'USER': os.getenv('DB_USER', 'default_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'default_password'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}
    - Etape 3 : Créer un fichier .env à la racine du projet et ajouter ces variables :
DJANGO_SECRET_KEY=ultra-secret-key-123
DJANGO_DEBUG=False # en production seulement
DB_NAME=pastry_app
DB_USER=cattiaux
DB_PASSWORD=cattiauxmartin
DB_HOST=localhost
DB_PORT=5432
    - Etape 4 : Ajouter .env à .gitignore : echo ".env" >> .gitignore

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

### Gestion des stores : Ajout d'une Contrainte d’Unicité sur Store en Production

Problème actuel : unique_together est actuellement défini au niveau de l’API via serializers.py, mais pas directement en base​. 
Impact : Risque d'incohérences si la validation API est contournée.
Solution : Ajouter une contrainte unique en base de données
    - Étape 1 : Modifier models.py avec l'ajout d'une contrainte unique :
    class Meta:
        constraints = [models.UniqueConstraint(fields=["store_name", "city", "zip_code"], name="unique_store_per_location")]
        indexes = [models.Index(fields=["store_name", "city", "zip_code"])]
    - Étape 2 : Générer la migration avec makemigrations et migrate

### Différence entre unique_together et UniqueConstraint
-> Remplacer dans le code unique_together par UniqueConstraint car c’est la méthode moderne et plus puissante.

- unique_together = ("field1", "field2")
    Avantages : Facile à écrire, rétrocompatible	
    Inconvénients : Vieille syntaxe, risque d’être dépréciée
- UniqueConstraint(fields=["field1", "field2"], name="constraint_name")	
    Avantages : Plus flexible (on peut ajouter des filtres condition, deferrable...), recommandé par Django	
    Inconvénient : Un peu plus verbeux


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
Contexte
    Actuellement, certaines validations sont effectuées dans clean() et save(). 
    Cependant, si elles ne sont pas bien optimisées, elles peuvent ralentir l'application, 
    notamment lors d’opérations en masse ou d'accès fréquents à la base de données.

Améliorations à mettre en place
1. Limiter les requêtes en base dans clean()
    - Éviter les .filter().exists() répétitifs qui génèrent plusieurs requêtes SQL.
    - Préférer une approche qui utilise un count() si nécessaire.
2. Ne pas appeler full_clean() dans save() systématiquement
    - full_clean() peut être coûteux si save() est exécuté en masse.
    - À utiliser uniquement si la validation ne peut être garantie autrement (ex : API ouverte, gestion externe).
3. Regrouper les traitements pour éviter des accès multiples à la base
    - Si plusieurs vérifications nécessitent des requêtes SQL, les regrouper en une seule requête plutôt que d’en exécuter plusieurs dans clean().
4. Éviter full_clean() lors d’imports en masse
    - Remplacer .save() sur chaque objet par bulk_create() pour améliorer les performances.
    - Exemple :
        objs = [SubRecipe(**data) for data in dataset]
        SubRecipe.objects.bulk_create(objs)  # Évite full_clean(), optimise l’insertion

Actions à mener
    - Identifier les clean() et save() qui contiennent des requêtes répétitives et les optimiser.
    - Supprimer les full_clean() inutiles dans save(), sauf si une validation stricte est requise.
    - Utiliser bulk_create() pour les traitements de masse.



### Analyse et implémentation des filter_backends dans les ViewSet
Contexte :
Pour l’instant, certaines vues utilisent uniquement SearchFilter pour les recherches textuelles (via ?search=), 
mais les besoins métiers futurs (notamment côté admin ou frontend) nécessiteront de 
filtrer précisément les objets via des champs spécifiques (ex: ?pan_type=ROUND, ?brand=...).

Objectif :
Passer en revue tous les ViewSet exposés par l’API afin d’identifier les cas où il serait pertinent d'ajouter :
- DjangoFilterBackend pour les filtres champ à champ (filterset_fields)
- Des filtres plus complexes (via FilterSet custom si besoin)

Étapes à faire :
- Auditer tous les ViewSet de l’API
    - Identifier les besoins métiers en termes de filtrage pour chaque entité
    - Ex: pouvoir filtrer les recettes par label, category, ou les ingrédients par store, unit, etc.
- Ajouter progressivement filter_backends = [DjangoFilterBackend] là où nécessaire
- Écrire des tests de filtrage simples (ex : ?champ=valeur retourne bien les bons objets)
- Documenter les filtres disponibles pour chaque endpoint (utile pour le frontend ou Swagger)

À noter :
- Peut être combiné avec SearchFilter pour conserver les recherches textuelles
- L’ajout de filterset_fields ne casse rien : c’est rétrocompatible



### API de suggestion de moules en fonction du volume cible
Contexte :
Actuellement, le modèle Pan permet de stocker et calculer le volume de chaque moule (volume_cm3_cache).
Cependant, il n'existe pas encore d'API permettant de suggérer dynamiquement des moules adaptés à un volume cible.

Objectif :
Permettre à l'utilisateur de trouver rapidement les moules compatibles avec :
- un volume cible (ex : après avoir recalculé les ingrédients)
- un nombre de portions converti en volume
- des contraintes physiques (ex : max 1400 cm³)

À faire :
1. Créer une vue dédiée (PanSuggestionAPIView) en lecture seule
2. Permettre le passage d’un paramètre ?target_volume=...
3. Appliquer une tolérance (10% par défaut) pour retourner les Pan dont volume_cm3_cache est proche du volume demandé
4. Ajouter l’endpoint dans les routes sous : /pans/suggestions/
5. (Optionnel) Ajouter des filtres supplémentaires (ex: pan_type, brand)

Bénéfice :
- Meilleure UX pour adapter les recettes
- Système intelligent de correspondance entre recette et matériel utilisateur
- Base technique réutilisable pour d'autres fonctionnalités (calcul de portions, adaptation dynamique)


### Calcul automatique du multiplicateur de quantité en fonction du moule : 
Développer une fonction qui, en se basant sur les volumes des moules source et cible, calcule automatiquement le multiplicateur de quantité.

### Calcul automatique du multiplicateur de quantité en fonction de la quantité d'un ingrédient spécifique 

### Ecrire des tests API pour la route POST /recipes/adapt/

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