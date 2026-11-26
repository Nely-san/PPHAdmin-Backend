import logging
from rest_framework.permissions import BasePermission
from users.models import UserPagePermission

logger = logging.getLogger(__name__)

FIELD_MAP = {"add": "can_add", "edit": "can_edit", "delete": "can_delete"}
READONLY_PAGE_KEYS = frozenset({"dashboard", "audit-logs"})

def user_has_module_permission(user, module, action="edit"):
    """Backward-compatible shim. Delegates to has_page_permission.

    Note: default action is 'edit' to preserve the historical signature
    of this function. Do not change without auditing every caller.
    """
    return has_page_permission(user, module, action)

def has_page_permission(user, page_key, action="view"):
    """Single permission resolver. Fail-closed.

    Behavior: 
      - Hard denials: None/anonymous/inactive/archived/no-role -> False.
      - Superuser or SUPER_ADMIN role -> True.
      - If a UserPagePermission override row exists for (user, page_key):
          - Non-view actions on READONLY_PAGE_KEYS -> False.
          - can_view=False -> False.
          - action='view' -> True.
          - else -> getattr(row, FIELD_MAP[action]).
      - Otherwise fall back to role.permissions ∪ user.custom_permissions:
          - Preserves the historical behavior of the old
            user_has_module_permission: exact match, exact action match,
            'view' prefix match, and parent-module fallback.
          - READONLY_PAGE_KEYS still denies non-view on this branch.
    """
    if user is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_active", False) is False:
        return False
    if getattr(user, "is_archived", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if getattr(user, "role_id", None) is None:
        return False
    role = getattr(user, "role", None)
    if role is None:
        return False
    if role.code == "SUPER_ADMIN":
        return True

    if action == "view":
        field = "can_view"
    else:
        field = FIELD_MAP.get(action)
        if field is None:
            raise ValueError(f"Unknown action: {action}")

    user_row = UserPagePermission.objects.filter(
        user=user, page_key=page_key, is_archived=False
    ).first()

    if user_row is not None:
        # Override branch.
        if not user_row.can_view:
            return False
        if action == "view":
            return True
        if page_key in READONLY_PAGE_KEYS:
            return False
        return getattr(user_row, field)

    # Fallback branch: role + custom_permissions (historical behavior).
    role_codes = set(role.permissions.values_list("code", flat=True))
    custom_codes = set(user.custom_permissions.values_list("code", flat=True))
    all_codes = role_codes | custom_codes

    # Exact module match, or exact action match.
    if page_key in all_codes or f"{page_key}:{action}" in all_codes:
        granted = True
    elif action == "view" and any(c.startswith(f"{page_key}:") for c in all_codes):
        # Historical: any sub-permission grants view.
        granted = True
    elif ":" in page_key:
        # Historical: parent-module fallback.
        parent = page_key.split(":")[0]
        granted = (parent in all_codes) or (f"{parent}:{action}" in all_codes)
    else:
        granted = False

    if not granted:
        return False

    # Intentional Phase 2 behavior change: readonly pages deny non-view
    # even on the fallback branch.
    if action != "view" and page_key in READONLY_PAGE_KEYS:
        return False

    return True

class PagePermission(BasePermission):
    METHODS = {
        "GET": "view", "HEAD": "view", "OPTIONS": "view",
        "POST": "add", "PUT": "edit", "PATCH": "edit", "DELETE": "delete",
    }

    def has_permission(self, request, view):
        key = getattr(view, "page_key", None)
        if key is None:
            logger.warning(
                "View %s has no page_key; denying.",
                view.__class__.__name__,
            )
            return False
        action = self.METHODS.get(request.method)
        if action is None:
            return False
        return has_page_permission(request.user, key, action)
