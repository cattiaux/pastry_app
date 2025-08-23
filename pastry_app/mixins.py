from django.db.models import Q
from django.urls import reverse, path
from django.http import JsonResponse
from rest_framework.exceptions import PermissionDenied

class GuestUserRecipeMixin:
    """
    Mixin pour factoriser la gestion des recettes/ingrédients/moules/magasins multi-utilisateurs (user ou invité/guest_id).
    - Permet à un utilisateur connecté d'accéder à ses propres éléments + publiques + "de base".
    - Permet à un invité d'accéder aux éléments publiques, de base, et à ses propres éléments privées (par guest_id).
    - Attribue la recette à user ou guest_id lors de la création.
    - Forçage : les éléments créées par un invité sont privées par défaut, sauf si "public" est explicitement demandé.
    """
    def get_guest_id(self):
        """Récupère le guest_id depuis le header, les données du body ou les query params."""
        return (
            self.request.headers.get("X-Guest-Id")
            or self.request.headers.get("X-GUEST-ID")  # Certains navigateurs upper-case tout
            or self.request.data.get("guest_id")
            or self.request.query_params.get("guest_id")
        )

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # Recettes de l'utilisateur + publiques + de base
            return (self.queryset.model.objects.filter(Q(user=user) | Q(visibility="public") | Q(is_default=True)).distinct())
        else:
            guest_id = self.get_guest_id()
            qs = self.queryset.model.objects.filter(Q(visibility="public") | Q(is_default=True))
            if guest_id:
                # Ajoute ses recettes privées (en tant qu'invité identifié par guest_id)
                qs = qs | self.queryset.model.objects.filter(guest_id=guest_id, visibility="private")
            return qs.distinct()

    def perform_create(self, serializer):
        """
        Lors de la création :
        - Attribue à l'utilisateur connecté, OU à l'invité (guest_id).
        - Forçage : si invité, visibility="private" sauf si explicitement demandé "public" ET si tu l'acceptes.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.get_guest_id() if not user else None

        # Si le modèle n’a pas de champ visibility (Store/Ingredient/Pan éventuels), on n’impose rien.
        model_has_visibility = hasattr(serializer.Meta.model, "visibility")

        if model_has_visibility:
            visibility = (self.request.data.get("visibility") or "private").lower()
            # Invité ne peut pas publier
            if not user and visibility == "public":
                raise PermissionDenied("Un invité ne peut pas publier en public.")
            serializer.save(user=user, guest_id=guest_id, visibility=visibility)
        else:
            serializer.save(user=user, guest_id=guest_id)

        # visibility = self.request.data.get("visibility")

        # # Par défaut toujours "private", sauf si explicitement public
        # if not visibility or visibility != "public":
        #     visibility = "private"
        # save_kwargs = dict(user=user, guest_id=guest_id, visibility=visibility)
        # serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        model = serializer.Meta.model
        if hasattr(model, "visibility") and not user:
            new_visibility = (self.request.data.get("visibility") or "").lower()
            if new_visibility == "public":
                raise PermissionDenied("Un invité ne peut pas publier en public.")
        serializer.save()

class GuestUserReferenceMixin:
    """
    Mixin ultra-minimaliste pour gestion user/guest sur les modèles sans visibility.
    """

    def get_guest_id(self):
        """Récupère le guest_id depuis le header, les données du body ou les query params."""
        return (
            self.request.headers.get("X-Guest-Id")
            or self.request.headers.get("X-GUEST-ID")  # Certains navigateurs upper-case tout
            or self.request.data.get("guest_id")
            or self.request.query_params.get("guest_id")
        )

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.get_guest_id()
        return qs.filter(Q(user=user) | Q(guest_id=guest_id) | (Q(user__isnull=True) & Q(guest_id__isnull=True)))

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.get_guest_id()
        serializer.save(user=user, guest_id=guest_id)

class OverridableReferenceQuerysetMixin:
    """
    Pour les modèles à “base globale overridable”, fournit la logique DRY de merge privé + global sauf overridés.
    """

    def get_user_overridable_queryset(self, base_queryset):
        """
        base_queryset doit être le queryset du modèle complet (all())
        Renvoie : privés du user/guest + globales non overridées
        """
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.request.session.get('guest_id')
        # 1. Privés
        private_qs = base_queryset.filter(Q(user=user) | Q(guest_id=guest_id))
        # 2. Clefs déjà overridées
        private_keys = set((ref.ingredient_id, ref.unit) for ref in private_qs)
        # 3. Globales pas overridées
        global_qs = base_queryset.filter(user__isnull=True, guest_id__isnull=True)
        if private_keys:
            q_objects = Q()
            for (i, u) in private_keys:
                q_objects |= (Q(ingredient_id=i) & Q(unit=u))
            global_qs = global_qs.exclude(q_objects)
        # 4. Union (queryset combiné)
        return private_qs | global_qs

class AdminSuggestMixin:
    """
    Factorise:
      - l’endpoint JSON /suggest/ protégé par l’admin
      - l’injection de son URL dans le changelist via data-attribute
    Usage: class MyAdmin(AdminSuggestMixin, admin.ModelAdmin): pass
    """
    change_list_template = "admin/with_endpoints_change_list.html"
    suggest_limit = 10  # max résultats
    suggest_route_suffix = "suggest"  # segment d’URL

    # ---------- wiring UI ----------
    def get_suggest_url(self, request):
        """URL absolue nommée de l’endpoint /suggest/ de ce ModelAdmin."""
        return reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_{self.suggest_route_suffix}",
            current_app=self.admin_site.name,
        )

    def changelist_view(self, request, extra_context=None):
        """Injecte l’URL /suggest/ dans le template de liste."""
        extra_context = extra_context or {}
        extra_context["admin_api"] = {"suggest": self.get_suggest_url(request)}
        return super().changelist_view(request, extra_context=extra_context)

    # ---------- endpoint ----------
    def get_urls(self):
        """
        Ajoute l’endpoint JSON `/suggest/` (protégé par admin_view) pour l’autocomplétion
        de la barre de recherche du changelist courant.
        """
        urls = super().get_urls()
        extra = [
            path(
                f"{self.suggest_route_suffix}/",
                self.admin_site.admin_view(self.suggest_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_{self.suggest_route_suffix}",
            )
        ]
        return extra + urls

    # ---------- logique de suggestion ----------
    def get_suggest_fields(self):
        """
        Champs interrogés. Par défaut: self.search_fields.
        Surcharger si besoin (retourner un iterable de champs).
        """
        return getattr(self, "search_fields", ())

    def get_suggest_queryset(self):
        """QS de base pour les suggestions. Surcharge possible (ex: .only())."""
        return self.model.objects.all()

    def suggest_view(self, request):
        """
        Retourne JSON {"results": [...]}
        - Aggregue les suggestions issues de TOUS les champs de get_suggest_fields()
        - Gère les préfixes Django: '^'→istartswith, '='→iexact, sinon→icontains
        - Déduplique, tronque à suggest_limit
        """
        q = (request.GET.get("q") or "").strip()

        if len(q) < 2:
            return JsonResponse({"results": []})
        
        fields = list(self.get_suggest_fields())
        if not q or not fields:
            return JsonResponse({"results": []})

        limit = int(getattr(self, "suggest_limit", 10))
        base_qs = self.get_suggest_queryset()
        out = []

        for f in fields:
            raw = f.lstrip("^=@")
            if f.startswith("^"):
                flt = {f"{raw}__istartswith": q}
            elif f.startswith("="):
                flt = {f"{raw}__iexact": q}
            else:
                flt = {f"{raw}__icontains": q}

            vals = (base_qs.filter(**flt)
                            .values_list(raw, flat=True)
                            .distinct()
                            .order_by(raw)[:limit])
            out.extend(v for v in vals if v)

        seen, results = set(), []
        for v in out:
            s = str(v)
            if s not in seen:
                seen.add(s); results.append(s)
            if len(results) >= limit:
                break

        return JsonResponse({"results": results})
