from rest_framework import serializers
from django.db import IntegrityError
from django.db.models import Max
from django.utils.timezone import now
from .models import *
from .constants import UNIT_CHOICES
from pastry_app.tests.utils import normalize_case
# from .utils import update_related_instances

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
        """ Vérifie qu'au moins une ville (`city`) ou un code postal (`zip_code`) est renseigné. """
        # Si c'est un PATCH (mise à jour partielle), ne pas valider les champs absents
        if self.partial:
            return data
    
        data["city"] = data.get("city", "") or ""  # Convertit None en ""
        data["zip_code"] = data.get("zip_code", "") or ""

        if not data["city"] and not data["zip_code"]:
            raise serializers.ValidationError("Si un magasin est renseigné, vous devez indiquer une ville ou un code postal.", code="missing_location")
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
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    unit = serializers.ChoiceField(choices=UNIT_CHOICES)

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'recipe', 'ingredient', 'quantity', 'unit', 'display_name']
        extra_kwargs = {"recipe": {"read_only": True},}  # Une fois l'ingrédient ajouté à une recette, il ne peut pas être déplacé

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
    step_number = serializers.IntegerField(default=None, min_value=1)

    class Meta:
        model = RecipeStep
        fields = ['id', 'recipe', 'step_number', 'instruction', 'trick']
        extra_kwargs = {"recipe": {"read_only": True},}  # Une fois l'étape ajoutée, elle ne peut pas être déplacée

    def validate_instruction(self, value):
        """ Vérifie que l'instruction contient au moins 5 caractères. """
        if len(value) < 5:
            raise serializers.ValidationError("L'instruction doit contenir au moins 5 caractères.")
        return value

    def validate_step_number(self, value):
        """ Vérifie que `step_number` est bien consécutif. """
        if value is None:  # Éviter la comparaison `None > int`
            return value 
        
        recipe = self.initial_data.get("recipe")  # Récupérer la recette envoyée
        if recipe:
            last_step = RecipeStep.objects.filter(recipe=recipe).aggregate(Max("step_number"))["step_number__max"]
            if last_step is not None and value > last_step + 1:
                raise serializers.ValidationError("Step numbers must be consecutive.")
        return value

    def create(self, validated_data):
        """ Gère la création d'un `RecipeStep` en attribuant `step_number` automatiquement si nécessaire. """
        recipe = validated_data.get("recipe")
        # Auto-incrément de `step_number` si non fourni ou None
        if validated_data.get("step_number") is None:
            max_step = RecipeStep.objects.filter(recipe=recipe).aggregate(Max("step_number"))["step_number__max"]
            validated_data["step_number"] = 1 if max_step is None else max_step + 1
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """ Gère la mise à jour d'un `RecipeStep`, tout en validant `step_number` si changé. """
        step_number = validated_data.get("step_number", instance.step_number)
        # Vérifie si on essaye de modifier `step_number` en doublon
        if step_number != instance.step_number:
            if RecipeStep.objects.filter(recipe=instance.recipe, step_number=step_number).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError({"step_number": "Ce numéro d'étape existe déjà pour cette recette."})
        return super().update(instance, validated_data)

class SubRecipeSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    sub_recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = SubRecipe
        fields = ["id", "recipe", "sub_recipe", "quantity", "unit"]
        extra_kwargs = {"recipe": {"read_only": True},}  # La recette principale ne peut pas être modifiée

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
        if self.instance and "recipe" in data and self.instance.recipe.id != recipe:
            raise serializers.ValidationError({"recipe": "Recipe cannot be changed after creation."})

        return data

class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(source='recipeingredient_set', many=True)
    sub_recipes = SubRecipeSerializer(source='subrecipe_set', many=True)
    steps = RecipeStepSerializer(source='recipestep_set', many=True)
    pan = serializers.PrimaryKeyRelatedField(queryset=Pan.objects.all(), allow_null=True)

    class Meta:
        model = Recipe
        fields = ['recipe_name', 'chef', 'ingredients', 'steps', 'sub_recipes', 'default_volume', 'default_servings', 'pan']
    
    # def validate_pan(self, value):
    #     if isinstance(value, Pan):
    #         value = value.id
    #     if not (Pan.objects.filter(id=value).exists() or RoundPan.objects.filter(id=value).exists() or SquarePan.objects.filter(id=value).exists()):
    #         raise serializers.ValidationError("Invalid pan ID.")
    #     return value

    # def create(self, validated_data):
    #     ingredients_data = validated_data.pop('recipeingredient_set')
    #     steps_data = validated_data.pop('recipestep_set', [])
    #     sub_recipes_data = validated_data.pop('subrecipe_set', [])
    #     pan_id = validated_data.pop('pan', None)
    #     if pan_id is not None:
    #         validated_data['pan'] = Pan.objects.get(id=pan_id)
    #     recipe = Recipe.objects.create(**validated_data)

    #     for ingredient_data in ingredients_data:
    #         ingredient_data['ingredient'] = ingredient_data['ingredient'].id
    #         ingredient_serializer = RecipeIngredientSerializer(data=ingredient_data)
    #         if ingredient_serializer.is_valid():
    #             RecipeIngredient.objects.create(recipe=recipe, **ingredient_serializer.validated_data)
    #         else:
    #             raise serializers.ValidationError(ingredient_serializer.errors)

    #     for step_data in steps_data:
    #         RecipeStep.objects.create(recipe=recipe, **step_data)

    #     for sub_recipe_data in sub_recipes_data:
    #         SubRecipe.objects.create(recipe=recipe, **sub_recipe_data)

    #     return recipe

    # def update(self, instance, validated_data):
    #     ingredients_data = validated_data.pop('recipeingredient_set', [])
    #     steps_data = validated_data.pop('recipestep_set', [])
    #     sub_recipes_data = validated_data.pop('subrecipe_set', [])

    #     instance.recipe_name = validated_data.get('recipe_name', instance.recipe_name)
    #     instance.chef = validated_data.get('chef', instance.chef)
    #     instance.default_volume = validated_data.get('default_volume', instance.default_volume)
    #     instance.default_servings = validated_data.get('default_servings', instance.default_servings)
    #     pan_id = validated_data.get('pan', instance.pan.id if instance.pan else None)
    #     instance.pan = Pan.objects.get(id=pan_id) if pan_id else None
    #     instance.save()

    #     update_related_instances(instance, ingredients_data, 'recipeingredient_set', RecipeIngredient, RecipeIngredientSerializer, "recipe")
    #     update_related_instances(instance, steps_data, 'recipestep_set', RecipeStep, RecipeStepSerializer, "recipe")
    #     update_related_instances(instance, sub_recipes_data, 'subrecipe_set', SubRecipe, SubRecipeSerializer, "recipe")

    #     return instance

class PanSerializer(serializers.ModelSerializer):
    pan_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    volume_cm3 = serializers.FloatField(read_only=True)  # expose le volume calculé, non modifiable

    class Meta:
        model = Pan
        fields = [
            "id", "pan_name", "pan_type", "brand",
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
        if "brand" in data:
            data["brand"] = normalize_case(data["brand"])
        return super().to_internal_value(data)

    def validate(self, data):
        pan_type = data.get("pan_type", getattr(self.instance, "pan_type", None))

        # Champs requis par type
        if pan_type == "ROUND":
            for field in ["diameter", "height"]:
                if not data.get(field) and not getattr(self.instance, field, None):
                    raise serializers.ValidationError({field: "Ce champ est requis pour un moule rond."})
        elif pan_type == "RECTANGLE":
            for field in ["length", "width", "rect_height"]:
                if not data.get(field) and not getattr(self.instance, field, None):
                    raise serializers.ValidationError({field: "Ce champ est requis pour un moule rectangulaire."})
        elif pan_type == "CUSTOM":
            if not data.get("volume_raw") and not getattr(self.instance, "volume_raw", None):
                raise serializers.ValidationError({"volume_raw": "Volume requis pour un moule personnalisé."})
            if not data.get("unit") and not getattr(self.instance, "unit", None):
                raise serializers.ValidationError({"unit": "Unité requise pour un moule personnalisé."})
        else:
            raise serializers.ValidationError({"pan_type": "Type de moule invalide."})

        return data

