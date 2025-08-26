from rest_framework.authentication import BaseAuthentication
from django.contrib.auth.models import AnonymousUser

class GuestIdAuthentication(BaseAuthentication):
    """
    Expose request.guest_id si X-Guest-Id est présent. N'authentifie pas un user.

    Si le header X-Guest-Id est présent:
      - retourne (AnonymousUser, {"guest_id": ...})
      - attache request.guest_id pour le queryset/logic
    Sinon: retourne None → laisse les autres backends tenter.
    """    
    def authenticate(self, request):
        gid = (request.headers.get("X-Guest-Id")
               or request.headers.get("X_GUEST_ID")
               or request.headers.get("X_GUESTID"))
        if not gid:
            return None
        request.guest_id = gid
        return (AnonymousUser(), {"guest_id": gid})
