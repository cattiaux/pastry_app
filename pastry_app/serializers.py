# serializers.py
from rest_framework import serializers
from django.db import IntegrityError
from django.db.models import Index
from .models import Recipe, Pan, Ingredient, IngredientPrice, IngredientPriceHistory, Store, Category, Label, RecipeIngredient, RecipeStep, SubRecipe, RoundPan, SquarePan
from pastry_app.serializers import StoreSerializer
from .utils import get_pan_model, update_related_instances
from pastry_app.constants import CATEGORY_NAME_CHOICES, LABEL_NAME_CHOICES
from pastry_app.tests.utils import normalize_case
from django.utils.timezone import now

class StoreSerializer(serializers.ModelSerializer):
    """ Sérialise les magasins où sont vendus les ingrédients. """
    city = serializers.CharField(required=False, allow_blank=True)
    zip_code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Store
        fields = ["id", "store_name", "city", "zip_code"]

    def validate_store_name(self, value):
        """ Normalisation et validation du nom du magasin. """
        return normalize_case(value) if value else value

    def validate_city(self, value):
        """ Vérifie que la ville a au moins 2 caractères """
        if value and len(value) < 2:
            raise serializers.ValidationError("Le nom de la ville doit contenir au moins 2 caractères.")
        return value

class IngredientPriceSerializer(serializers.ModelSerializer):
    date = serializers.DateField(input_formats=['%Y-%m-%d'])
    store = StoreSerializer() # Sérialisation imbriquée des magasins

    class Meta:
        model = IngredientPrice
        fields = ['id', 'ingredient', 'brand_name', 'store', 'date', 'quantity', 'unit', 'price', "is_promo", "promotion_end_date"]

    def validate_quantity(self, value):
        """ Vérifie que la quantité est strictement positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    ### Déjjà gérer dans la méthode clean() du modèle
    # def validate_price(self, value):
    #     """ Vérifie que le prix est strictement positif. """
    #     if value <= 0:
    #         raise serializers.ValidationError("Price must be a positive number.")
    #     return value

    def validate_date(self, value):
        """ Vérifie que la date n'est pas dans le futur. """
        if value > now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_store(self, value):
        """ Vérifie que le magasin existe bien avant de l'associer à un prix"""
        if value and not Store.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Le magasin sélectionné n'existe pas en base. Veuillez le créer avant d'ajouter un prix.")
        return value

    def validate(self, data):
        """ Vérifie les contraintes métier (promotions, cohérence des données, etc.). """
        if data.get("promotion_end_date") and not data.get("is_promo"):
            raise serializers.ValidationError("Une date de fin de promotion nécessite que `is_promo=True`.")
        return data

    def update(self, instance, validated_data):
        """ Désactive la mise à jour des prix, impose la création d'un nouvel enregistrement. """
        raise serializers.ValidationError("Les prix des ingrédients ne peuvent pas être modifiés. Créez un nouvel enregistrement.")

class IngredientPriceHistorySerializer(serializers.ModelSerializer):
    """ Gère la validation et la sérialisation de l'historique des prix d'ingrédients. """

    class Meta:
        model = IngredientPriceHistory
        fields = ["id", "ingredient_price", "date", "price", "is_promo"]  # Champs exposés via l'API
        indexes = [Index(fields=["ingredient_price", "date"])]
        unique_together = ("ingredient_price", "date", "price")

    def validate(self, data):
        """ Vérifie qu'un prix identique ne soit pas enregistré inutilement. """
        ingredient_price = data.get("ingredient_price")
        new_price = data.get("price")
        date = data.get("date")

        # Récupérer le dernier prix en base
        last_price = IngredientPriceHistory.objects.filter(ingredient_price=ingredient_price).order_by("-date").first()

        # Si le prix est identique au dernier enregistré, refuser la requête
        if last_price and last_price.price == new_price:
            raise serializers.ValidationError("Ce prix est déjà enregistré.")

        # Vérifier qu'on ne crée pas un duplicata (même prix, même date, même ingrédient)
        if IngredientPriceHistory.objects.filter(ingredient_price=ingredient_price, date=date, price=new_price).exists():
            raise serializers.ValidationError("Cet enregistrement existe déjà.")

        return data
    
class CategorySerializer(serializers.ModelSerializer):
    category_type = serializers.CharField(required=False)

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'category_type', 'created_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['category_name'] = ret['category_name'].lower()
        return ret

    def create(self, validated_data):
        """ Vérifie l’unicité via l’API et capture IntegrityError pour plus de sécurité """
        if Category.objects.filter(category_name__iexact=validated_data["category_name"]).exists():
            raise serializers.ValidationError({"category_name": "Une catégorie avec ce nom existe déjà."})
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"category_name": "Erreur d’unicité en base. Contactez un administrateur."})

    def validate_category_name(self, value):
        """ Vérifie que 'category_name' est valide et vérifie si une autre catégorie existe déjà avec ce nom (insensible à la casse)"""
        value = " ".join(value.lower().strip().split())  # Normalisation

        # Vérifier que la catégorie existe bien dans CATEGORY_NAME_CHOICES
        if value not in CATEGORY_NAME_CHOICES:
            raise serializers.ValidationError("Cette catégorie n'est pas valide.")

        # Vérifier l'unicité du category_name (insensible à la casse)
        category_id = self.instance.id if self.instance else None
        if Category.objects.exclude(id=category_id).filter(category_name__iexact=value).exists():
            raise serializers.ValidationError("Category with this Category name already exists.")

        return value

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'label_name', 'label_type', 'created_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['label_name'] = ret['label_name'].lower()
        return ret
    
    def create(self, validated_data):
        """ Vérifie l’unicité via l’API et capture IntegrityError pour plus de sécurité """
        if Label.objects.filter(label_name__iexact=validated_data["label_name"]).exists():
            raise serializers.ValidationError({"label_name": "Un label avec ce nom existe déjà."})
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"label_name": "Erreur d’unicité en base. Contactez un administrateur."})

    def validate_label_name(self, value):
        """ Vérifie que 'label_name' est valide et vérifie si un autre label existe déjà avec ce nom (insensible à la casse)"""
        value = normalize_case(value)  # Normalisation

        # Vérifier que le label existe bien dans LABEL_NAME_CHOICES
        if value not in LABEL_NAME_CHOICES:
            raise serializers.ValidationError("Ce label n'est pas valide.")

        # Vérifier l'unicité du label_name (insensible à la casse)
        label_id = self.instance.id if self.instance else None
        if Label.objects.exclude(id=label_id).filter(label_name__iexact=value).exists():
            raise serializers.ValidationError("Label with this Label name already exists.")

        return value
    
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
    
    def to_representation(self, instance):
        """ Assure que l'affichage dans l'API est bien normalisé """
        representation = super().to_representation(instance)
        representation["ingredient_name"] = normalize_case(representation["ingredient_name"])
        return representation

class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    unit = serializers.CharField(max_length=50)

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'ingredient', 'quantity', 'unit']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate_recipe_name(self, value):
        if not value or value.isspace():
            raise serializers.ValidationError("Recipe name cannot be empty or only contain whitespace.")
        return value
    
class RecipeStepSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = RecipeStep
        fields = ['id', 'step_number', 'instruction', 'trick']

class SubRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    sub_recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = SubRecipe
        fields = ['id', 'sub_recipe', 'quantity']

class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(source='recipeingredient_set', many=True)
    sub_recipes = SubRecipeSerializer(source='subrecipe_set', many=True)
    steps = RecipeStepSerializer(source='recipestep_set', many=True)
    pan = serializers.PrimaryKeyRelatedField(queryset=Pan.objects.all(), allow_null=True)

    class Meta:
        model = Recipe
        fields = ['recipe_name', 'chef', 'ingredients', 'steps', 'sub_recipes', 'default_volume', 'default_servings', 'pan']
    
    def validate_pan(self, value):
        if isinstance(value, Pan):
            value = value.id
        if not (Pan.objects.filter(id=value).exists() or RoundPan.objects.filter(id=value).exists() or SquarePan.objects.filter(id=value).exists()):
            raise serializers.ValidationError("Invalid pan ID.")
        return value

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipeingredient_set')
        steps_data = validated_data.pop('recipestep_set', [])
        sub_recipes_data = validated_data.pop('subrecipe_set', [])
        pan_id = validated_data.pop('pan', None)
        if pan_id is not None:
            validated_data['pan'] = Pan.objects.get(id=pan_id)
        recipe = Recipe.objects.create(**validated_data)

        for ingredient_data in ingredients_data:
            ingredient_data['ingredient'] = ingredient_data['ingredient'].id
            ingredient_serializer = RecipeIngredientSerializer(data=ingredient_data)
            if ingredient_serializer.is_valid():
                RecipeIngredient.objects.create(recipe=recipe, **ingredient_serializer.validated_data)
            else:
                raise serializers.ValidationError(ingredient_serializer.errors)

        for step_data in steps_data:
            RecipeStep.objects.create(recipe=recipe, **step_data)

        for sub_recipe_data in sub_recipes_data:
            SubRecipe.objects.create(recipe=recipe, **sub_recipe_data)

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('recipeingredient_set', [])
        steps_data = validated_data.pop('recipestep_set', [])
        sub_recipes_data = validated_data.pop('subrecipe_set', [])

        instance.recipe_name = validated_data.get('recipe_name', instance.recipe_name)
        instance.chef = validated_data.get('chef', instance.chef)
        instance.default_volume = validated_data.get('default_volume', instance.default_volume)
        instance.default_servings = validated_data.get('default_servings', instance.default_servings)
        pan_id = validated_data.get('pan', instance.pan.id if instance.pan else None)
        instance.pan = Pan.objects.get(id=pan_id) if pan_id else None
        instance.save()

        update_related_instances(instance, ingredients_data, 'recipeingredient_set', RecipeIngredient, RecipeIngredientSerializer, "recipe")
        update_related_instances(instance, steps_data, 'recipestep_set', RecipeStep, RecipeStepSerializer, "recipe")
        update_related_instances(instance, sub_recipes_data, 'subrecipe_set', SubRecipe, SubRecipeSerializer, "recipe")

        return instance

class PanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pan
        fields = ['pan_name', 'pan_type']

    def create(self, validated_data):
        pan_type = validated_data.get('pan_type')
        pan_model = get_pan_model(pan_type)
        pan = pan_model.objects.create(**validated_data)
        return pan

    def update(self, instance, validated_data):
        pan_type = validated_data.get('pan_type', instance.pan_type)
        pan_model = get_pan_model(instance.pan_type)
        pan = pan_model.objects.get(id=instance.id)
        for key, value in validated_data.items():
            setattr(pan, key, value)
        pan.save()
        return pan
    
class RoundPanSerializer(serializers.ModelSerializer):
    class Meta(PanSerializer.Meta):
        model = RoundPan
        fields = PanSerializer.Meta.fields + ['diameter', 'height']

class SquarePanSerializer(serializers.ModelSerializer):
    class Meta(PanSerializer.Meta):
        model = SquarePan
        fields = PanSerializer.Meta.fields + ['length', 'width', 'height']
