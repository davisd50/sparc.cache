from zope.interface import Interface, Attribute

class IsupportCentralDateTime(Interface):
    """Basic ZCA wrapper around a support central date string"""
    key = Attribute("Support central date key name string")