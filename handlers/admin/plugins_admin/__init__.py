# plugins_admin alt paketi (manage + pset)
from . import manage, pset


def register(bot):
    manage.register(bot)
    pset.register(bot)
