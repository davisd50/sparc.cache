from zope.interface import Attribute
from zope.lifecycleevent import IObjectCreatedEvent
from zope.lifecycleevent import IObjectModifiedEvent

class ICacheObjectCreatedEvent(IObjectCreatedEvent):
    """zope.lifecycle compatible event for new cache item creation"""
    area = Attribute('ICacheArea that was updated')

class ICacheObjectModifiedEvent(IObjectModifiedEvent):
    """zope.lifecycle compatible event for new cache item modifications"""
    area = Attribute('ICacheArea that was updated')