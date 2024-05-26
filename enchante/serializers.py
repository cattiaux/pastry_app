# serializers.py
from rest_framework import serializers
from django.db import IntegrityError
from .models import Recipe, Pan, Ingredient, IngredientPrice, Category, Label, RecipeIngredient, RecipeStep, SubRecipe, RoundPan, SquarePan, PanServing
from .utils import get_pan_model, update_related_instances

class IngredientPriceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    date = serializers.DateField(input_formats=['%Y-%m-%d'])

    class Meta:
        model = IngredientPrice
        fields = ['id','brand', 'store_name', 'date', 'quantity', 'unit', 'price']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be a positive number.")
        return value

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['name']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['name'] = ret['name'].lower()
        return ret

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['name']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['name'] = ret['name'].lower()
        return ret

class IngredientSerializer(serializers.ModelSerializer):
    prices = IngredientPriceSerializer(source='ingredientprice_set', many=True)
    categories = CategorySerializer(many=True)
    labels = LabelSerializer(many=True)

    class Meta:
        model = Ingredient
        fields = ['ingredient_name', 'categories', 'labels', 'prices']

    def create(self, validated_data):
        try:
            prices_data = validated_data.pop('ingredientprice_set')
            categories_data = validated_data.pop('categories')
            labels_data = validated_data.pop('labels')
            ingredient = Ingredient.objects.create(**validated_data)

            for category_data in categories_data:
                category, created = Category.objects.get_or_create(name=category_data["name"].lower())
                ingredient.categories.add(category)

            for label_data in labels_data:
                label, created = Label.objects.get_or_create(name=label_data["name"].lower())
                ingredient.labels.add(label)

            for price_data in prices_data:
                IngredientPrice.objects.create(ingredient=ingredient, **price_data)

        except IntegrityError:
            raise serializers.ValidationError("An ingredient with this name already exists.")
        return ingredient

    def update(self, instance, validated_data):
        prices_data = validated_data.pop('ingredientprice_set', [])
        categories_data = validated_data.pop('categories', [])
        labels_data = validated_data.pop('labels', [])
        instance.ingredient_name = validated_data.get('ingredient_name', instance.ingredient_name)
        instance.save()

        update_related_instances(instance, prices_data, 'ingredientprice_set', IngredientPrice, IngredientPriceSerializer, 'ingredient')

        instance.categories.clear()
        for category_data in categories_data:
            category, created = Category.objects.get_or_create(name=category_data["name"].lower())
            instance.categories.add(category)

        instance.labels.clear()
        for label_data in labels_data:
            label, created = Label.objects.get_or_create(name=label_data["name"].lower())
            instance.labels.add(label)

        return instance

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
