# ============================================
# KingTG UserBot Service - Handlers Package
# ============================================

from .user import register_user_handlers
from .admin import register_admin_handlers

__all__ = ['register_user_handlers', 'register_admin_handlers']
