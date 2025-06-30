from rest_framework import serializers
from django.db import IntegrityError
from django.db.models import Max
from django.utils.timezone import now
from .models import *
from .constants import UNIT_CHOICES
from pastry_app.tests.utils import normalize_case

class StoreSerializer(serializers.ModelSerializer):
    """ Sérialise les magasins où sont vendus les ingrédients. """
    store_name = serializers.CharField(
        required=True,  # Champ obligatoire
        allow_blank=False,  # Interdit ""
        error_messages={"blank": "This field cannot be blank.", "required": "This field is required.", "null": "This field may not be null."}
    )
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    zip_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)    

    class Meta:
        model = Store
        fields = ["id", "store_name", "city", "zip_code"]

    def validate_store_name(self, value):
        """ Normalisation et validation du nom du magasin. """
        value = normalize_case(value) if value else value
        if len(value) < 2:
            raise serializers.ValidationError("Le nom du magasin doit contenir au moins 2 caractères.")
        return value

    def validate_city(self, value):
        """ Normalisation + Vérifie que la ville a au moins 2 caractères """
        if not value:  # Gérer None et les valeurs vides
            return value  # Laisser DRF gérer l'erreur si nécessaire

        value = normalize_case(value)  # Maintenant, on est sûr que value n'est pas None
        if len(value) < 2:
            raise serializers.ValidationError("Le nom de la ville doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        """
        Vérifie, lors de la création ou de la mise à jour d'un Store :
        - Qu'au moins une ville (`city`) ou un code postal (`zip_code`) est renseigné,
        - Que le magasin (défini par le triplet `store_name`, `city`, `zip_code`) n'existe pas déjà en base.
        La validation s'applique aussi bien en création (POST) qu'en modification partielle ou complète (PATCH/PUT).
        """        
        # Récupérer les valeurs actuelles (instance) si absentes de data (cas PATCH)
        store_name = data.get("store_name", getattr(self.instance, "store_name", ""))
        city = data.get("city", getattr(self.instance, "city", ""))
        zip_code = data.get("zip_code", getattr(self.instance, "zip_code", ""))

        # Appliquer la normalisation car le champ PATCH peut ne pas passer par validate_<field>
        store_name = normalize_case(store_name) if store_name else ""
        city = normalize_case(city) if city else ""

        # Validation métier : il faut au moins une city OU un zip_code
        if not city and not zip_code:
            raise serializers.ValidationError(
                "Si un magasin est renseigné, vous devez indiquer une ville ou un code postal.",
                code="missing_location"
            )

        # Vérification de l'unicité, même pour PATCH (mise à jour partielle)
        qs = Store.objects.filter(store_name=store_name, city=city, zip_code=zip_code)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ce magasin existe déjà.")
        
        return data

class IngredientPriceSerializer(serializers.ModelSerializer):
    ingredient = serializers.SlugRelatedField(queryset=Ingredient.objects.all(), slug_field="ingredient_name")
    store = serializers.PrimaryKeyRelatedField(required=False, queryset=Store.objects.all(), default=None)
    date = serializers.DateField(required=False, default=now().date, input_formats=['%Y-%m-%d'])
    brand_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None) 

    class Meta:
        model = IngredientPrice
        fields = ['id', 'ingredient', 'brand_name', 'store', 'date', 'quantity', 'unit', 'price', "is_promo", "promotion_end_date"]
    
    def validate_quantity(self, value):
        """ S'assure que `quantity` est un float valide et vérifie que la quantité est strictement positive"""
        try:
            value = float(value)
        except ValueError:
            raise serializers.ValidationError("Quantity must be a positive number.")

        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate_price(self, value):
        """ Vérifie que le prix est strictement positif. """
        if value <= 0:
            raise serializers.ValidationError("Price must be a positive number.")
        return value

    def validate_date(self, value):
        """ Vérifie que la date n'est pas dans le futur. """
        if value and value > now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_store(self, value):
        """ Vérifie que le magasin existe bien avant de l'associer à un prix"""
        if value and not Store.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Le magasin sélectionné n'existe pas en base. Veuillez le créer avant d'ajouter un prix.")
        return value
    
    def validate_brand_name(self, value):
        """ Normalisation + Vérifie que le nom de marque a au moins 2 caractères """
        if not value: 
            return ""  
        
        value = normalize_case(value)  # Maintenant, on est sûr que value n'est pas None
        if len(value) < 2:
            raise serializers.ValidationError("Le nom de la marque doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        """ Vérifie les contraintes métier (promotions, cohérence des données, etc.). """
        if data.get("promotion_end_date") and not data.get("is_promo"):
            raise serializers.ValidationError("Une date de fin de promotion nécessite que `is_promo=True`.")
        
        # Permettre à `date` d'être optionnel.
        if "date" not in data:
            data["date"] = now().date()  # Assigner automatiquement la date du jour

        ### Validation personnalisée pour gérer l'unicité sans bloquer DRF.
        # Récupérer les champs qui définissent l’unicité
        ingredient = data.get("ingredient")
        store = data.get("store")
        brand_name = data.get("brand_name", "")
        quantity = data.get("quantity")
        unit = data.get("unit")
        price = data.get("price")
        is_promo = data.get("is_promo", False)
        promo_end_date = data.get("promotion_end_date")

        # Vérifier si un `IngredientPrice` existe déjà pour cette combinaison
        existing_price = IngredientPrice.objects.filter(
            ingredient=ingredient, store=store, brand_name=brand_name, quantity=quantity, unit=unit
        ).first()

        if existing_price:
            if price != existing_price.price or is_promo != existing_price.is_promo:  # Cas où le prix ou `is_promo` change → Archivage + Nouveau prix
                pass  # Ne pas lever d'erreur, car ce sera géré dans `create()` de la `view`
            elif promo_end_date != existing_price.promotion_end_date:  # Cas où seule `promotion_end_date` change → Mise à jour directe
                pass  # Pas d'erreur, la vue mettra à jour directement `promotion_end_date`
            else:  # Cas où l'on essaie de créer un duplicata strict
                raise serializers.ValidationError("must make a unique set.")
        
        return data

    def update(self, instance, validated_data):
        """ Désactive la mise à jour des prix, impose la création d'un nouvel enregistrement. """
        raise serializers.ValidationError("Les prix des ingrédients ne peuvent pas être modifiés. Créez un nouvel enregistrement.")

class IngredientPriceHistorySerializer(serializers.ModelSerializer):
    """ Gère la validation et la sérialisation de l'historique des prix d'ingrédients. """

    class Meta:
        model = IngredientPriceHistory
        fields = ['id', 'ingredient', 'brand_name', 'store', 'date', 'quantity', 'unit', 'price', "is_promo", "promotion_end_date"]
        read_only_fields = fields  # Empêche toute modification via l'API
    
class CategorySerializer(serializers.ModelSerializer):
    parent_category = serializers.SlugRelatedField(queryset=Category.objects.all(), slug_field="category_name", allow_null=True, required=False)

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'category_type', 'parent_category']

    def to_internal_value(self, data):
        """ Normalise AVANT validation. """
        data = data.copy()  # Rend le QueryDict mutable

        if "category_name" in data:
            data["category_name"] = normalize_case(data["category_name"])
        if "category_type" in data:
            data["category_type"] = normalize_case(data["category_type"])
        if "parent_category" in data and isinstance(data["parent_category"], str):
            data["parent_category"] = normalize_case(data["parent_category"]) 
        return super().to_internal_value(data)

    def validate_category_name(self, value):
        """ Vérifie que 'category_name' existe en base et empêche les utilisateurs non-admins d'ajouter des catégories. """
        request = self.context.get("request")
        
        # Vérifie si la catégorie existe déjà en base
        category_exists = Category.objects.exclude(id=self.instance.id if self.instance else None).filter(category_name__iexact=value).exists()
        if category_exists:
            raise serializers.ValidationError("Une catégorie avec ce nom existe déjà.")

        # Seuls les admins peuvent ajouter de nouvelles catégories
        if not request.user.is_staff and not category_exists:
            raise serializers.ValidationError("Vous ne pouvez choisir qu'une catégorie existante.")

        return value

    def validate_category_type(self, value):
        """ Vérifie que `category_type` est dans les choix valides. """
        valid_choices = dict(Category.CATEGORY_CHOICES).keys()
        if value not in valid_choices:
            raise serializers.ValidationError(f"`category_type` doit être l'une des valeurs suivantes : {', '.join(valid_choices)}.")
        return value

    def create(self, validated_data):
        """ Seuls les admins peuvent créer une catégorie. """
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent créer des catégories.")

        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"category_name": "Cette catégorie existe déjà."})

    def update(self, instance, validated_data):
        # Seuls les admins peuvent modifier une catégorie.
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent modifier une catégorie.")

        # Empêche la modification de `category_name` vers un nom déjà existant.
        new_name = validated_data.get("category_name", instance.category_name)
        if normalize_case(new_name) != normalize_case(instance.category_name):
            if Category.objects.exclude(id=instance.id).filter(category_name__iexact=new_name).exists():
                raise serializers.ValidationError({"category_name": "Une catégorie avec ce nom existe déjà."})

        return super().update(instance, validated_data)

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'label_name', 'label_type']

    def to_internal_value(self, data):
        """ Normalise AVANT validation. """
        data = data.copy()  # Rend le QueryDict mutable

        if "label_name" in data:
            data["label_name"] = normalize_case(data["label_name"])
        if "label_type" in data:
            data["label_type"] = normalize_case(data["label_type"])
        return super().to_internal_value(data)

    def validate_label_name(self, value):
        """ Vérifie que 'label_name' existe en base et empêche les utilisateurs non-admins d'ajouter des labels. """
        request = self.context.get("request")
        
        # Vérifie si la catégorie existe déjà en base
        label_exists = Label.objects.exclude(id=self.instance.id if self.instance else None).filter(label_name__iexact=value).exists()
        if label_exists:
            raise serializers.ValidationError("Un label avec ce nom existe déjà.")

        # Seuls les admins peuvent ajouter de nouveaux labels
        if not request.user.is_staff and not label_exists:
            raise serializers.ValidationError("Vous ne pouvez choisir qu'un label existant.")

        return value

    def validate_label_type(self, value):
        """ Vérifie que `label_type` est dans les choix valides. """
        valid_choices = dict(Label.LABEL_CHOICES).keys()
        if value not in valid_choices:
            raise serializers.ValidationError(f"`label_type` doit être l'une des valeurs suivantes : {', '.join(valid_choices)}.")
        return value

    def create(self, validated_data):
        """ Seuls les admins peuvent créer un label. """
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent créer des labels.")

        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"label_name": "Ce label existe déjà."})

    def update(self, instance, validated_data):
        # Seuls les admins peuvent modifier un label.
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent modifier un label.")

        # Empêche la modification de `label_name` vers un nom déjà existant.
        new_name = validated_data.get("label_name", instance.label_name)
        if normalize_case(new_name) != normalize_case(instance.label_name):
            if Label.objects.exclude(id=instance.id).filter(label_name=new_name).exists():
                raise serializers.ValidationError({"label_name": "Un label avec ce nom existe déjà."})

        return super().update(instance, validated_data)

class IngredientSerializer(serializers.ModelSerializer):
    prices = IngredientPriceSerializer(many=True, read_only=True)
    categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), many=True, required=False) #PrimaryKeyRelatedField assure la vérification de l'existence de la category par DRF
    labels = serializers.PrimaryKeyRelatedField(queryset=Label.objects.all(), many=True, required=False)

    class Meta:
        model = Ingredient
        fields = ['id', 'ingredient_name', 'categories', 'labels', 'prices']
    
    def validate_ingredient_name(self, value):
        """ Vérifie que l'ingrédient n'existe pas déjà (insensible à la casse), sauf s'il s'agit de la mise à jour du même ingrédient. """
        value = normalize_case(value)  # Normalisation : minuscule + suppression espaces inutiles

        ingredient_id = self.instance.id if self.instance else None  # Exclure l'ID courant en cas de mise à jour
        if Ingredient.objects.exclude(id=ingredient_id).filter(ingredient_name__iexact=value).exists():
            raise serializers.ValidationError("Un ingrédient avec ce nom existe déjà.")
        return value

    def validate_categories(self, value):
        """ Personnalise le message d'erreur si une catégorie n'existe pas. """
        existing_categories_ids = set(Category.objects.values_list("id", flat=True))
        for category in value:
            if category.id not in existing_categories_ids:
                raise serializers.ValidationError(f"La catégorie '{category.category_name}' n'existe pas. Veuillez la créer d'abord.")
        return value

    def validate_labels(self, value):
        """ Personnalise le message d'erreur si un label n'existe pas """
        existing_labels_ids = set(Label.objects.values_list("id", flat=True))
        for label in value:
            if label.id not in existing_labels_ids:
                raise serializers.ValidationError(f"Le label '{label.label_name}' n'existe pas. Veuillez le créer d'abord.")
        return value

    def validate(self, data):
        """ Permet de ne pas valider les champs absents dans le cas d'un PATCH. """
        if self.partial:
            return data
        return data

    def to_representation(self, instance):
        """ Assure que l'affichage dans l'API est bien normalisé """
        representation = super().to_representation(instance)
        representation["ingredient_name"] = normalize_case(representation["ingredient_name"])
        return representation

class RecipeIngredientSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), required=False)
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    unit = serializers.ChoiceField(choices=UNIT_CHOICES)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'recipe', 'ingredient', 'quantity', 'unit', 'display_name']
        extra_kwargs = {"recipe": {"read_only": True},}  # Une fois l'ingrédient ajouté à une recette, il ne peut pas être déplacé

    def get_fields(self):
        """Rend recipe optionnel via URL imbriquée."""
        fields = super().get_fields()

        # Cas de contexte parent serializer → suppression complète du champ
        if self.context.get("is_nested", False):
            fields.pop("recipe", None)
        # Cas endpoint imbriqué (ex: /recipes/<id>/steps/)
        elif "view" in self.context:
            view = self.context["view"]
            if hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
                fields["recipe"].required = False

        return fields

    def run_validation(self, data=serializers.empty):
        """Injecte recipe depuis l’URL."""
        view = self.context.get("view")
        if view and hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
            data = data.copy()
            data["recipe"] = view.kwargs["recipe_pk"]

        result = super().run_validation(data)
        return result

    def validate_quantity(self, value):
        """ Vérifie que la quantité est strictement positive. """
        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate(self, data):
        """ Vérifie que l’ingrédient, la quantité et l’unité sont bien présents (sauf en PATCH). """
        request = self.context.get("request", None)
        is_partial = request and request.method == "PATCH"  # Vérifie si c'est un PATCH

        if not is_partial:  # Ne pas exiger tous les champs en PATCH
            if "ingredient" not in data:
                raise serializers.ValidationError({"ingredient": "Un ingrédient est obligatoire."})
            if "quantity" not in data:
                raise serializers.ValidationError({"quantity": "Une quantité est obligatoire."})
            if "unit" not in data:
                raise serializers.ValidationError({"unit": "Une unité de mesure est obligatoire."})
            
        return data
    
class RecipeStepSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    step_number = serializers.IntegerField(default=None, min_value=1)

    class Meta:
        model = RecipeStep
        fields = ['id', 'recipe', 'step_number', 'instruction', 'trick']

    def get_fields(self):
        """Rend recipe optionnel via URL imbriquée."""
        fields = super().get_fields()

        # Cas de contexte parent serializer → suppression complète du champ
        if self.context.get("is_nested", False):
            fields.pop("recipe", None)
        # Cas endpoint imbriqué (ex: /recipes/<id>/steps/)
        elif "view" in self.context:
            view = self.context["view"]
            if hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
                fields["recipe"].required = False

        return fields

    def run_validation(self, data=serializers.empty):
        """Injecte recipe depuis l’URL."""
        view = self.context.get("view")
        if view and hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
            data = data.copy()
            data["recipe"] = view.kwargs["recipe_pk"]

        result = super().run_validation(data)
        return result

    def validate_instruction(self, value):
        """ Vérifie que l'instruction contient au moins 5 caractères. """
        if len(value) < 5:
            raise serializers.ValidationError("L'instruction doit contenir au moins 5 caractères.")
        return value

    def validate(self, data):
        """
        - Vérifie que `step_number` est consécutif.
        - Vérifie qu'il n'y a pas déjà une étape avec ce numéro pour cette recette (unicité recipe/step_number).
        """
        recipe = data.get("recipe")
        step_number = data.get("step_number")

        if recipe and step_number is not None:
            # Unicité : interdit de dupliquer une étape
            qs = RecipeStep.objects.filter(recipe=recipe, step_number=step_number)
            # Si c'est un update, on exclut l'instance en cours
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"step_number": "Ce numéro d'étape existe déjà pour cette recette."})

            # Consécutivité
            last_step = RecipeStep.objects.filter(recipe=recipe).aggregate(Max("step_number"))["step_number__max"]
            if last_step is not None and step_number > last_step + 1:
                raise serializers.ValidationError({"step_number": "Step numbers must be consecutive."})

        return data
    
    def create(self, validated_data):
        """ Gère la création d'un `RecipeStep` en attribuant `step_number` automatiquement si nécessaire. """
        # Auto-incrément de `step_number` si non fourni ou None
        if validated_data.get("step_number") is None:
            max_step = RecipeStep.objects.filter(recipe=validated_data.get("recipe")).aggregate(Max("step_number"))["step_number__max"]
            validated_data["step_number"] = 1 if max_step is None else max_step + 1

        return super().create(validated_data)

class SubRecipeSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), required=False)
    sub_recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = SubRecipe
        fields = ["id", "recipe", "sub_recipe", "quantity", "unit"]
        extra_kwargs = {"recipe": {"read_only": True},}  # La recette principale ne peut pas être modifiée

    def get_fields(self):
        """Rend recipe optionnel via URL imbriquée."""
        fields = super().get_fields()

        # Cas de contexte parent serializer → suppression complète du champ
        if self.context.get("is_nested", False):
            fields.pop("recipe", None)
        # Cas endpoint imbriqué (ex: /recipes/<id>/steps/)
        elif "view" in self.context:
            view = self.context["view"]
            if hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
                fields["recipe"].required = False

        return fields

    def run_validation(self, data=serializers.empty):
        """Injecte recipe depuis l’URL."""
        view = self.context.get("view")
        if view and hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
            data = data.copy()
            data["recipe"] = view.kwargs["recipe_pk"]

        result = super().run_validation(data)
        return result

    def validate_sub_recipe(self, value):
        """ Vérifie qu'une recette ne peut pas être sa propre sous-recette """
        if self.instance and self.instance.recipe == value:
            raise serializers.ValidationError("Une recette ne peut pas être sa propre sous-recette.")
        return value

    def validate_quantity(self, value):
        """ Vérifie que la quantité est strictement positive """
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être strictement positive.")
        return value

    def validate(self, data):
        """ 
        Vérifie des règles métier :
        1. Une recette ne peut pas être sa propre sous-recette.
        2. Le champ `recipe` ne peut pas être modifié après création.
        """
        recipe = data.get("recipe")
        sub_recipe = data.get("sub_recipe")

        # Interdiction d'une recette en sous-recette d'elle-même
        if recipe and sub_recipe and recipe.id == sub_recipe.id:
            raise serializers.ValidationError({"sub_recipe": "Une recette ne peut pas être sa propre sous-recette."})

        # Empêcher la modification du champ `recipe` après création
        if self.instance and "recipe" in self.initial_data:
            incoming_recipe_id = data.get("recipe")
            if incoming_recipe_id and self.instance.recipe.id != incoming_recipe_id:  # On lève l’erreur que si le client fournit explicitement une valeur différente pour recipe
                raise serializers.ValidationError({"recipe": "Recipe cannot be changed after creation."})

        return data

class RecipeSerializer(serializers.ModelSerializer):
    # Champs simples
    recipe_name = serializers.CharField()
    chef_name = serializers.CharField()
    context_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    trick = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    servings_min = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    servings_max = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    
    # Relations simples
    pan = serializers.PrimaryKeyRelatedField(queryset=Pan.objects.all(), allow_null=True, required=False)
    parent_recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), allow_null=True, required=False)
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Recipe.categories.rel.model.objects.all(), required=False)
    labels = serializers.PrimaryKeyRelatedField(many=True, queryset=Recipe.labels.rel.model.objects.all(), required=False)
    ingredients = RecipeIngredientSerializer(many=True, required=False, context={"is_nested": True}, source="recipe_ingredients")
    steps = RecipeStepSerializer(many=True, required=False, context={"is_nested": True})
    sub_recipes = SubRecipeSerializer(many=True, required=False, context={"is_nested": True}, source="main_recipes")

    # Utilisateur et visibilité
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_id = serializers.CharField(read_only=True)
    visibility = serializers.ChoiceField(choices=[('private', 'Privée'), ('public', 'Publique')])
    is_default = serializers.BooleanField(read_only=True)

    class Meta:
        model = Recipe
        fields = ["id", 
                  "recipe_name", "chef_name", "context_name", 
                  "source", "recipe_type", "parent_recipe", 
                  "servings_min", "servings_max", "description", "trick", "image", 
                  "pan", "categories", "labels", "ingredients", "steps", "sub_recipes", 
                  "created_at", "updated_at",
                  "user", "guest_id", "visibility", "is_default"]
        read_only_fields = ["created_at", "updated_at"]    

    def __init__(self, *args, **kwargs):
        """Supprime recipe en mode nested."""
        super().__init__(*args, **kwargs)
        if "steps" in self.fields:
            self.fields["steps"].child.context.update({"is_nested": True})
        if "recipe_ingredients" in self.fields:
            self.fields["recipe_ingredients"].child.context.update({"is_nested": True})
        if "main_recipes" in self.fields:
            self.fields["main_recipes"].child.context.update({"is_nested": True})

    def to_internal_value(self, data):
        data = data.copy()
        if "recipe_name" in data:
            data["recipe_name"] = normalize_case(data["recipe_name"])
        if "chef_name" in data:
            data["chef_name"] = normalize_case(data["chef_name"])
        return super().to_internal_value(data)

    def validate_recipe_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Le nom de la recette doit contenir au moins 3 caractères.")
        return value

    def validate_chef_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Le nom du chef doit contenir au moins 3 caractères.")
        return value

    def validate_description(self, value):
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("doit contenir au moins 10 caractères.")
        return value

    def validate_trick(self, value):
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("doit contenir au moins 10 caractères.")
        return value

    def validate_context_name(self, value):
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("Le contexte doit contenir au moins 3 caractères.")
        return value

    def validate_source(self, value):
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("La source doit contenir au moins 3 caractères.")
        return value

    def validate(self, data):
        parent = data.get("parent_recipe")
        rtype = data.get("recipe_type", getattr(self.instance, "recipe_type", "BASE"))

        if parent and parent == self.instance:
            raise serializers.ValidationError("Une recette ne peut pas être sa propre version précédente.")
        if parent and rtype != "VARIATION":
            raise serializers.ValidationError("Une recette avec un parent doit être de type VARIATION.")
        if rtype == "VARIATION" and not parent:
            raise serializers.ValidationError("Une recette de type VARIATION doit avoir une parent_recipe.")

        min_val = data.get("servings_min")
        max_val = data.get("servings_max")
        if min_val and max_val and min_val > max_val:
            raise serializers.ValidationError("Le nombre de portions minimum ne peut pas être supérieur au maximum.")

        # Validation d’unicité logique (soft-match insensible à la casse)
        # Fusion champ par champ pour obtenir l'état final du triplet unique
        name = normalize_case(data.get("recipe_name") or (self.instance and self.instance.recipe_name))
        chef = normalize_case(data.get("chef_name") or (self.instance and self.instance.chef_name))
        context = normalize_case(data.get("context_name") or (self.instance and self.instance.context_name))
        recipe_id = self.instance.id if self.instance else None

        # Si une autre recette a les mêmes valeurs → erreur
        if Recipe.objects.exclude(id=recipe_id).filter(recipe_name__iexact=name, chef_name__iexact=chef, context_name__iexact=context).exists():
            raise serializers.ValidationError("Une recette avec ce nom, ce chef et ce contexte existe déjà.")
        
        # Vérification du contenu minimum (à la création uniquement)
        if not self.instance:
            ingredients = data.get("recipe_ingredients", [])
            sub_recipes = data.get("main_recipes", [])
            steps = data.get("steps", [])

            if not (ingredients or sub_recipes):
                raise serializers.ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
            if not (steps or sub_recipes):
                raise serializers.ValidationError("Une recette doit contenir au moins une étape ou une sous-recette.")

        # Boucle indirecte
        def has_cyclic_parent(instance, new_parent):
            current = new_parent
            while current:
                if current == instance:
                    return True
                current = current.parent_recipe
            return False

        if parent and self.instance and has_cyclic_parent(self.instance, parent):
            raise serializers.ValidationError("Cycle détecté dans les versions de recette.")

        if parent and rtype != "VARIATION":
            raise serializers.ValidationError("Une recette avec une parent_recipe doit être de type VARIATION.")
        if rtype == "VARIATION" and not parent:
            raise serializers.ValidationError("Une recette de type VARIATION doit avoir une parent_recipe.")

        return data

    def create(self, validated_data):
        # Extraction des sous-objets
        ingredients_data = validated_data.pop("recipe_ingredients", [])
        steps_data = validated_data.pop("steps", [])
        subrecipes_data = validated_data.pop("main_recipes", [])
        categories = validated_data.pop("categories", [])
        labels = validated_data.pop("labels", [])
        
        # Création de la recette
        recipe = Recipe.objects.create(**validated_data)
        recipe.categories.set(categories)
        recipe.labels.set(labels)

        # Création des ingrédients
        RecipeIngredient.objects.bulk_create([RecipeIngredient(recipe=recipe, **ingredient) for ingredient in ingredients_data])
        # Création des étapes
        RecipeStep.objects.bulk_create([RecipeStep(recipe=recipe, **step) for step in steps_data])
        # Création des sous-recettes via modèle intermédiaire
        SubRecipe.objects.bulk_create([SubRecipe(recipe=recipe, **sub) for sub in subrecipes_data])

        return recipe

    def update(self, instance, validated_data):
        request = self.context.get("request")
        is_partial = request.method == "PATCH" if request else False

        # --- Gestion des sous-objets
        ingredients_data = validated_data.pop("recipe_ingredients", [])
        steps_data = validated_data.pop("steps", [])
        subrecipes_data = validated_data.pop("main_recipes", [])
        categories = validated_data.pop("categories", None)
        labels = validated_data.pop("labels", None)

        # --- Validation stricte en PATCH : pas de sous-objets autorisés ici
        if is_partial:
            forbidden_fields = {
                "recipe_ingredients": "Utilisez /recipes/<id>/ingredients/",
                "steps": "Utilisez /recipes/<id>/steps/",
                "main_recipes": "Utilisez /recipes/<id>/sub-recipes/"
            }
            for field in forbidden_fields:
                if field in self.initial_data:
                    raise serializers.ValidationError({field: forbidden_fields[field]})

        # --- Mise à jour des champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # --- M2M
        if categories is not None:
            instance.categories.set(categories)
        if labels is not None:
            instance.labels.set(labels)

        # --- Si PUT : suppression + recréation des sous-objets
        if not is_partial:
            if not ingredients_data and not subrecipes_data:
                raise serializers.ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
            if not steps_data and not subrecipes_data:
                raise serializers.ValidationError("Une recette doit contenir au moins une étape ou une sous-recette.")

            instance.recipe_ingredients.all().delete()
            instance.steps.all().delete()
            instance.main_recipes.all().delete()

            RecipeIngredient.objects.bulk_create([
                RecipeIngredient(recipe=instance, **data) for data in ingredients_data
            ])
            RecipeStep.objects.bulk_create([
                RecipeStep(recipe=instance, **data) for data in steps_data
            ])
            SubRecipe.objects.bulk_create([
                SubRecipe(recipe=instance, **data) for data in subrecipes_data
            ])

        return instance

    # def update(self, instance, validated_data):
    #     request = self.context.get("request")
    #     is_partial = request.method == "PATCH" if request else False

    #     # 1. Récupération des sous-objets et M2M fournis dans la requête
    #     ingredients_data = validated_data.pop("recipe_ingredients", [])
    #     steps_data = validated_data.pop("steps", [])
    #     subrecipes_data = validated_data.pop("main_recipes", None)
    #     categories = validated_data.pop("categories", None)
    #     labels = validated_data.pop("labels", None)

    #     # 2. Mise à jour des champs simples
    #     for attr, value in validated_data.items():
    #         setattr(instance, attr, value)
    #     instance.save()

    #     # 3. Mise à jour des M2M si fourni
    #     if categories is not None:
    #         instance.categories.set(categories)
    #     if labels is not None:
    #         instance.labels.set(labels)

    #     # 4. Remplacement total (PUT) ou partiel (PATCH)
    #     if not is_partial:  # PUT : remplacement total des blocs 
    #         # Vérification métier avant suppression
    #         if not ingredients_data and not subrecipes_data:
    #             raise serializers.ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
    #         if not steps_data and not subrecipes_data:
    #             raise serializers.ValidationError("Une recette doit contenir au moins une étape ou une sous-recette.")

    #         # Suppression totale
    #         instance.recipe_ingredients.all().delete()
    #         instance.main_recipes.all().delete()
    #         instance.steps.all().delete()

    #         # Re-création
    #         RecipeIngredient.objects.bulk_create([RecipeIngredient(recipe=instance, **ingredient) for ingredient in ingredients_data])
    #         RecipeStep.objects.bulk_create([RecipeStep(recipe=instance, **step) for step in steps_data])
    #         SubRecipe.objects.bulk_create([SubRecipe(recipe=instance, **sub) for sub in subrecipes_data])
    #     else:
    #         # PATCH — supprimer uniquement ce qui est fourni
    #         if "recipe_ingredients" in self.initial_data:                
    #             instance.recipe_ingredients.all().delete()
    #             RecipeIngredient.objects.bulk_create([RecipeIngredient(recipe=instance, **ingredient) for ingredient in ingredients_data])
    #         if "steps" in self.initial_data:
    #             if not steps_data and not instance.main_recipes.exists():
    #                 raise serializers.ValidationError("Une recette doit avoir au moins une étape ou une sous-recette.")
    #             instance.steps.all().delete()
    #             RecipeStep.objects.bulk_create([RecipeStep(recipe=instance, **step) for step in steps_data])
    #         if "main_recipes" in self.initial_data:
    #             instance.main_recipes.all().delete()
    #             SubRecipe.objects.bulk_create([SubRecipe(recipe=instance, **sub) for sub in subrecipes_data])

    #     return instance

class PanSerializer(serializers.ModelSerializer):
    pan_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pan_brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    volume_cm3 = serializers.FloatField(read_only=True)  # expose le volume calculé, non modifiable
    units_in_mold = serializers.IntegerField(min_value=1, required=False, default=1)

    class Meta:
        model = Pan
        fields = [
            "id", "pan_name", "pan_type", "pan_brand", 'units_in_mold',
            "diameter", "height",
            "length", "width", "rect_height",
            "volume_raw", "unit",
            "volume_cm3", "volume_cm3_cache"
        ]
        read_only_fields = ["volume_cm3", "volume_cm3_cache"]

    def to_internal_value(self, data):
        data = data.copy()
        if "pan_name" in data:
            data["pan_name"] = normalize_case(data["pan_name"])
        if "pan_brand" in data:
            data["pan_brand"] = normalize_case(data["pan_brand"])
        return super().to_internal_value(data)

    def validate_pan_name(self, value):
        value = normalize_case(value)
        pan_id = self.instance.id if self.instance else None
        if Pan.objects.exclude(id=pan_id).filter(pan_name__iexact=value).exists():
            raise serializers.ValidationError("Un moule avec ce nom existe déjà.")
        
        if value and len(value) < 2:
            raise serializers.ValidationError("Le nom du moule doit contenir au moins 2 caractères.")

        return value

    def validate_pan_brand(self, value):
        if value and len(value) < 2:
            raise serializers.ValidationError("Le nom de la marque doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        pan_type = data.get("pan_type", getattr(self.instance, "pan_type", None))

        # Champs requis par type
        if pan_type == "ROUND":
            for field in ["diameter", "height"]:
                if not data.get(field) and not getattr(self.instance, field, None):
                    raise serializers.ValidationError({field: "Ce champ est requis pour un moule rond."})
            for forbidden in ["length", "width", "rect_height", "volume_raw", "unit"]:
                if data.get(forbidden) is not None:
                    raise serializers.ValidationError({forbidden: "Ce champ n'est pas autorisé pour un moule rond."})

        elif pan_type == "RECTANGLE":
            for field in ["length", "width", "rect_height"]:
                if not data.get(field) and not getattr(self.instance, field, None):
                    raise serializers.ValidationError({field: "Ce champ est requis pour un moule rectangulaire."})
            for forbidden in ["diameter", "height", "volume_raw", "unit"]:
                if data.get(forbidden) is not None:
                    raise serializers.ValidationError({forbidden: "Ce champ n'est pas autorisé pour un moule rectangulaire."})

        elif pan_type == "CUSTOM":
            if not data.get("volume_raw") and not getattr(self.instance, "volume_raw", None):
                raise serializers.ValidationError({"volume_raw": "Volume requis pour un moule personnalisé."})
            if not data.get("unit") and not getattr(self.instance, "unit", None):
                raise serializers.ValidationError({"unit": "Unité requise pour un moule personnalisé."})
            for forbidden in ["diameter", "height", "length", "width", "rect_height"]:
                if data.get(forbidden) is not None:
                    raise serializers.ValidationError({forbidden: "Ce champ n'est pas autorisé pour un moule personnalisé."})

        else:
            raise serializers.ValidationError({"pan_type": "Type de moule invalide."})

        return data

class PanEstimationSerializer(serializers.Serializer):
    pan_id = serializers.IntegerField(required=False)
    pan_type = serializers.ChoiceField(choices=["ROUND", "RECTANGLE", "OTHER"], required=False)

    diameter = serializers.FloatField(required=False)
    height = serializers.FloatField(required=False)

    length = serializers.FloatField(required=False)
    width = serializers.FloatField(required=False)
    rect_height = serializers.FloatField(required=False)

    volume_raw = serializers.FloatField(required=False)

    def validate(self, data):
        if not data.get("pan_id") and not data.get("pan_type") and not data.get("volume_raw"):
            raise serializers.ValidationError("Vous devez fournir un pan_id OU un pan_type avec dimensions OU un volume_raw.")
        return data

class PanSuggestionSerializer(serializers.Serializer):
    target_servings = serializers.IntegerField(required=True, min_value=1)

    def validate_target_servings(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le nombre de portions doit être supérieur à 0.")
        return value

class RecipeAdaptationByIngredientSerializer(serializers.Serializer):
    recipe_id = serializers.IntegerField(required=True)
    ingredient_constraints = serializers.DictField(
        child=serializers.FloatField(),
        help_text="Dictionnaire sous la forme {ingredient_id: quantité_disponible}"
    )


