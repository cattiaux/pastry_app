# reset total puis import
# python manage.py seed_yaml --dir pastry_app/data --mode reset --verbosity 2

# upsert (mise à jour incrémentale)
# python manage.py seed_yaml --dir pastry_app/data --mode upsert --verbosity 2

from __future__ import annotations
from pathlib import Path
import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from pastry_app.models import Category, Label, Ingredient, Pan, Recipe, RecipeStep, RecipeIngredient, SubRecipe, RecipeCategory, RecipeLabel
from pastry_app.constants import UNIT_CHOICES, SUBRECIPE_UNIT_CHOICES

# --- Units choices ---
try:
    VALID_UNITS = {k for k, _ in UNIT_CHOICES}
    VALID_SUB_UNITS = {k for k, _ in SUBRECIPE_UNIT_CHOICES}
except Exception:
    # Fallback par introspection des choix de champ
    VALID_UNITS = {k for k, _ in RecipeIngredient._meta.get_field("unit").choices}
    VALID_SUB_UNITS = {k for k, _ in SubRecipe._meta.get_field("unit").choices}

class Command(BaseCommand):
    help = "Peuple la base depuis YAML. Modes: upsert (défaut) ou reset."

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True, help="Dossier contenant les YAML")
        parser.add_argument("--mode", choices=["upsert", "reset"], default="upsert")
        parser.add_argument("--dry-run", action="store_true")

    # -------------------- Utils lecture --------------------
    def _read_yaml_file(self, base_no_ext: Path, root_key: str | None) -> list[dict]:
        """
        Charge base_no_ext + .yml|.yaml. Accepte:
          - liste top-level
          - dict top-level avec clé `root_key` (ex: {'recipes':[...]}).
        """
        for ext in (".yml", ".yaml"):
            p = base_no_ext.with_suffix(ext)
            if p.exists():
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                if data is None:
                    return []
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    if root_key and root_key in data:
                        return data[root_key] or []
                    # si clé inconnue, retourne le premier bloc liste trouvé
                    for v in data.values():
                        if isinstance(v, list):
                            return v
                    return []
        return []

    # -------------------- Helpers ORM --------------------
    @staticmethod
    def _ci(qs, field: str, value: str | None):
        if not value:
            return None
        return qs.filter(**{f"{field}__iexact": value}).first()

    def _require_admin(self):
        admin = get_user_model().objects.filter(is_staff=True).first()
        if not admin:
            raise CommandError("Aucun utilisateur admin (is_staff=True) trouvé.")
        return admin

    # -------------------- RESET --------------------
    def _reset_db(self):
        self.stdout.write("[reset] suppression des relations…")
        RecipeIngredient.objects.all().delete()
        RecipeStep.objects.all().delete()
        SubRecipe.objects.all().delete()
        RecipeLabel.objects.all().delete()
        RecipeCategory.objects.all().delete()

        self.stdout.write("[reset] suppression des objets…")
        Recipe.objects.all().delete()
        Pan.objects.all().delete()
        Ingredient.objects.all().delete()
        Label.objects.all().delete()
        Category.objects.all().delete()
        self.stdout.write(self.style.WARNING("[reset] base vidée"))

    # -------------------- UPSERTS atomiques --------------------
    def _upsert_category(self, admin, c: dict):
        parent = self._ci(Category.objects, "category_name", c.get("parent_category"))
        obj = self._ci(Category.objects, "category_name", c["category_name"])
        if obj:
            changed = False
            if obj.category_type != c["category_type"]:
                obj.category_type = c["category_type"]; changed = True
            if obj.parent_category_id != (parent.id if parent else None):
                obj.parent_category = parent; changed = True
            if changed:
                obj.save(update_fields=["category_type", "parent_category"])
            self.stdout.write(f"[upd] Category: {obj.category_name}")
        else:
            Category.objects.create(
                category_name=c["category_name"],
                category_type=c["category_type"],
                parent_category=parent,
                created_by=admin,
            )
            self.stdout.write(f"[new] Category: {c['category_name']}")

    def _upsert_label(self, admin, l: dict):
        obj = self._ci(Label.objects, "label_name", l["label_name"])
        if obj:
            lt = l.get("label_type", obj.label_type)
            if obj.label_type != lt:
                obj.label_type = lt
                obj.save(update_fields=["label_type"])
            self.stdout.write(f"[upd] Label: {obj.label_name}")
        else:
            Label.objects.create(
                label_name=l["label_name"],
                label_type=l.get("label_type", "both"),
                created_by=admin,
            )
            self.stdout.write(f"[new] Label: {l['label_name']}")

    def _upsert_ingredient(self, i: dict) -> Ingredient:
        obj = self._ci(Ingredient.objects, "ingredient_name", i["ingredient_name"])
        if obj:
            fields = []
            for k in ("visibility", "is_default"):
                if k in i and getattr(obj, k) != i[k]:
                    setattr(obj, k, i[k]); fields.append(k)
            if fields:
                obj.save(update_fields=fields)
            self.stdout.write(f"[upd] Ingredient: {obj.ingredient_name}")
            return obj
        obj = Ingredient.objects.create(
            ingredient_name=i["ingredient_name"],
            visibility=i.get("visibility", "private"),
            is_default=i.get("is_default", False),
        )
        self.stdout.write(f"[new] Ingredient: {obj.ingredient_name}")
        return obj

    def _upsert_pan(self, p: dict):
        obj = self._ci(Pan.objects, "pan_name", p.get("pan_name"))
        payload = dict(
            pan_type=p["pan_type"],
            pan_brand=p.get("pan_brand"),
            units_in_mold=p.get("units_in_mold", 1),
            volume_raw=p.get("volume_raw"),
            is_total_volume=p.get("is_total_volume", False),
            unit=p.get("unit"),
            visibility=p.get("visibility", "private"),
        )
        if obj:
            for k, v in payload.items():
                setattr(obj, k, v)
            obj.save()
            self.stdout.write(f"[upd] Pan: {obj.pan_name or '(sans nom)'}")
        else:
            Pan.objects.create(pan_name=p.get("pan_name"), **payload)
            self.stdout.write(f"[new] Pan: {p.get('pan_name') or '(sans nom)'}")

    def _match_recipe(self, r: dict) -> Recipe | None:
        return Recipe.objects.filter(
            recipe_name__iexact=r["recipe_name"],
            chef_name__iexact=(r.get("chef_name") or ""),
            context_name__iexact=(r.get("context_name") or ""),
        ).first()

    def _upsert_recipe_header(self, r: dict) -> Recipe:
        obj = self._match_recipe(r)
        payload = dict(
            source=r.get("source"),
            recipe_type=r.get("recipe_type", "BASE"),
            context_name=r.get("context_name", ""),
            servings_min=r.get("servings_min"),
            servings_max=r.get("servings_max"),
            pan_quantity=r.get("pan_quantity", 1),
            total_recipe_quantity=r.get("total_recipe_quantity"),
            visibility=r.get("visibility", "private"),
            is_default=r.get("is_default", False),
        )
        if obj:
            for k, v in payload.items():
                setattr(obj, k, v)
            obj.save()
            self.stdout.write(f"[upd] Recipe: {obj.recipe_name}")
            return obj
        obj = Recipe.objects.create(
            recipe_name=r["recipe_name"], chef_name=r.get("chef_name"), **payload
        )
        self.stdout.write(f"[new] Recipe: {obj.recipe_name}")
        return obj

    # -------------------- Validation YAML logique --------------------
    def _validate_steps(self, rec_name: str, steps: list[dict]):
        if not steps:
            return
        nums = [int(s["step_number"]) for s in steps]
        if nums[0] != 1 or nums != list(range(1, len(nums) + 1)):
            raise CommandError(f"{rec_name}: step_number doit être 1..N sans trou (reçu {nums}).")

    def _validate_ing_line(self, rec_name: str, it: dict):
        q = it.get("quantity")
        u = it.get("unit")
        if q is None or u is None:
            raise CommandError(f"{rec_name}: ingr '{it.get('ingredient')}' requiert quantity ET unit.")
        try:
            qf = float(q)
        except Exception:
            raise CommandError(f"{rec_name}: quantity non numérique pour '{it.get('ingredient')}' -> {q}")
        if qf <= 0:
            raise CommandError(f"{rec_name}: quantity doit être > 0 pour '{it.get('ingredient')}'.")
        if u not in VALID_UNITS:
            raise CommandError(f"{rec_name}: unité inconnue '{u}' pour '{it.get('ingredient')}'.")
        return qf, u

    def _validate_sub_line(self, rec_name: str, sr: dict):
        q = sr.get("quantity"); u = sr.get("unit")
        if q is None or u is None:
            raise CommandError(f"{rec_name}: sub_recipe '{sr}' requiert quantity ET unit.")
        try:
            qf = float(q)
        except Exception:
            raise CommandError(f"{rec_name}: quantity sub_recipe non numérique -> {q}")
        if qf <= 0:
            raise CommandError(f"{rec_name}: quantity sub_recipe doit être > 0.")
        if u not in VALID_SUB_UNITS:
            raise CommandError(f"{rec_name}: unité sub_recipe inconnue '{u}'.")
        return qf, u

    # -------------------- Relations (replace) --------------------
    def _replace_relations(self, rec: Recipe, r: dict, by_ing: dict[str, Ingredient], by_rec: dict[str, Recipe]):
        # Steps
        RecipeStep.objects.filter(recipe=rec).delete()
        steps = r.get("steps", [])
        self._validate_steps(rec.recipe_name, steps)
        for s in steps:
            RecipeStep.objects.create(
                recipe=rec,
                step_number=int(s["step_number"]),
                instruction=s["instruction"],
                trick=s.get("trick"),
            )

        # Ingredients
        RecipeIngredient.objects.filter(recipe=rec).delete()
        for it in r.get("ingredients", []):
            qf, u = self._validate_ing_line(rec.recipe_name, it)
            iname = it["ingredient"]
            ing = by_ing.get(iname.lower()) or self._ci(Ingredient.objects, "ingredient_name", iname)
            if not ing:
                ing = Ingredient.objects.create(ingredient_name=iname)
            RecipeIngredient.objects.create(recipe=rec, ingredient=ing, quantity=qf, unit=u)

        # Sub-recipes
        SubRecipe.objects.filter(recipe=rec).delete()
        for sr in r.get("sub_recipes", []):
            child_name = sr.get("recipe_name") or sr.get("sub_recipe")
            child = by_rec.get(child_name.lower()) or self._ci(Recipe.objects, "recipe_name", child_name)
            if not child:
                raise CommandError(f"{rec.recipe_name}: sous-recette introuvable '{child_name}'.")
            qf, u = self._validate_sub_line(rec.recipe_name, sr)
            SubRecipe.objects.create(recipe=rec, sub_recipe=child, quantity=qf, unit=u)

    # -------------------- MAIN --------------------
    @transaction.atomic
    def handle(self, *args, **opts):
        base = Path(opts["dir"]).resolve()
        self.stdout.write(f"[seed] data dir: {base}")
        self.stdout.write(f"[seed] exists={base.exists()}")

        admin = self._require_admin()

        # lecture
        cats = self._read_yaml_file(base / "categories", "categories")
        labs = self._read_yaml_file(base / "labels", "labels")
        ings = self._read_yaml_file(base / "ingredients", "ingredients")
        pans = self._read_yaml_file(base / "pans", "pans")
        recs = self._read_yaml_file(base / "recipes", "recipes")
        self.stdout.write(f"[seed] loaded: cats={len(cats)} labs={len(labs)} ings={len(ings)} pans={len(pans)} recs={len(recs)}")
        if not any([cats, labs, ings, pans, recs]):
            raise CommandError(f"Aucune donnée chargée depuis {base}.")

        if opts["mode"] == "reset":
            self._reset_db()

        # Catégories / Labels
        for c in cats:
            self._upsert_category(admin, c)
        for l in labs:
            self._upsert_label(admin, l)

        # Ingrédients
        by_ing: dict[str, Ingredient] = {}
        for i in ings:
            ing = self._upsert_ingredient(i)
            by_ing[ing.ingredient_name.lower()] = ing

        # Pans
        for p in pans:
            self._upsert_pan(p)

        # Recettes, passe 1: en-têtes
        by_rec: dict[str, Recipe] = {}
        for r in recs:
            rec = self._upsert_recipe_header(r)
            by_rec[rec.recipe_name.lower()] = rec

        # Recettes, passe 2: relations + Calcul du total
        cache = {}
        for r in recs:
            rec = by_rec[r["recipe_name"].lower()]
            self._replace_relations(rec, r, by_ing, by_rec)

            # --- calcule et enregistre total_recipe_quantity ---
            try:
                res = rec.compute_and_set_total_quantity(
                    force=True, save=True, cache=cache, collect_warnings=True
                )
                total, notes = res if isinstance(res, tuple) else (res, [])
                self.stdout.write(f"[total] {rec.recipe_name}: {total:.2f} g")
                if notes:
                    self.stdout.write(f"[warn] {rec.recipe_name}: {len(notes)} conversions ignorées")
            except ValidationError as e:
                # Si tu préfères bloquer l'import sur erreur, remplace le WARNING par un raise
                self.stdout.write(self.style.WARNING(f"[total] {rec.recipe_name}: calcul ignoré ({e})"))

        if opts.get("dry_run"):
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry-run: rollback effectué, aucune écriture persistée."))
            return

        self.stdout.write(self.style.SUCCESS("Import YAML terminé."))

