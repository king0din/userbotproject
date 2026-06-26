# User handlers paketi (user.py'dan bölündü)
from . import menu, login, plugins_user, help


def register_user_handlers(bot):
    menu.register(bot)
    login.register(bot)
    plugins_user.register(bot)
    help.register(bot)
