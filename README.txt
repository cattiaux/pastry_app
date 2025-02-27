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
