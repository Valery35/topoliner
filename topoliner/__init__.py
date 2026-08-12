# -*- coding: utf-8 -*-
def classFactory(iface):
    from .plugin import TopolinerPlugin
    return TopolinerPlugin(iface)
