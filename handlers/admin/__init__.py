# Admin handlers paketi (admin.py'dan bölündü)
from . import settings, users, plugins_admin, post, system


def register_admin_handlers(bot):
    settings.register(bot)
    users.register(bot)
    plugins_admin.register(bot)
    post.register(bot)
    system.register(bot)
