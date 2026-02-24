# ============================================
# KingTG UserBot Service - Userbot Package
# ============================================

# Smart Session Manager (yeni optimizeli versiyon)
from .smart_manager import smart_session_manager, SmartSessionManager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
UserbotManager = SmartSessionManager

# Plugin Manager
from .plugins import plugin_manager, PluginManager

__all__ = [
    'userbot_manager', 'UserbotManager',
    'smart_session_manager', 'SmartSessionManager',
    'plugin_manager', 'PluginManager'
]
