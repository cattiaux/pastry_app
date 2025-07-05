from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrGuestOrReadOnly(BasePermission):
    """
    - Un objet ne peut être modifié que par son propriétaire authentifié OU par l'invité qui l'a créé (via guest_id).
    - Lecture seule autorisée pour tous.
    """
    def has_object_permission(self, request, view, obj):
        # Lecture seule autorisée pour tout le monde
        if request.method in SAFE_METHODS:
            return True
        # Utilisateur authentifié
        if request.user.is_authenticated:
            return obj.user == request.user
        # Sinon, mode invité : compare le guest_id fourni à celui enregistré sur l'objet
        guest_id = request.headers.get("X-Guest-Id") or request.data.get("guest_id")
        return obj.guest_id and obj.guest_id == guest_id

class CanSoftHideRecipeOrIsOwnerOrGuest(BasePermission):
    """
    - Pour les recettes de base (is_default), autorise tout user ou invité identifié à soft-hide (DELETE).
    - Sinon : modif/suppression réservée au propriétaire ou à l'invité créateur (via guest_id).
    - Lecture seule pour tous.
    """
    def has_object_permission(self, request, view, obj):
        print("Checking permissions for object:", obj)
        # Lecture seule toujours autorisée
        if request.method in SAFE_METHODS:
            return True
        print("Request method:", request.method)
        print("Object is_default:", getattr(obj, "is_default", False))

        # Cas spécial : recette de base (is_default=True) ET delete
        if request.method == "DELETE" and getattr(obj, "is_default", False):
            print("Recette de base, autorisation soft-hide")
            if request.user.is_authenticated or (request.headers.get("X-Guest-Id") or request.data.get("guest_id")):
                return True

        # Comportement classique (propriétaire ou guest_id)
        if request.user.is_authenticated:
            return obj.user == request.user
        guest_id = request.headers.get("X-Guest-Id") or request.data.get("guest_id")
        return obj.guest_id and obj.guest_id == guest_id

class IsNotDefaultInstance(BasePermission):
    """
    Interdit la modification/suppression des objets 'de base' (is_default=True).
    S'applique à tous les modèles qui possèdent un champ booléen 'is_default'.
    """
    def has_object_permission(self, request, view, obj):
        # Si l'objet a is_default=True => lecture seule
        if getattr(obj, 'is_default', False):
            return request.method in SAFE_METHODS 
        return True
    
class IsAdminOrReadOnly(BasePermission):
    """
    Autorise l'écriture uniquement aux admins.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff