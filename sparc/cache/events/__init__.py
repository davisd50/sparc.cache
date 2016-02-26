from zope.interface import implements
from zope.lifecycleevent import ObjectCreatedEvent
from zope.lifecycleevent import ObjectModifiedEvent
from interfaces import ICacheObjectCreatedEvent
from interfaces import ICacheObjectModifiedEvent

class CacheObjectCreatedEvent(ObjectCreatedEvent):
    implements(ICacheObjectCreatedEvent)
    def __init__(self, object, area):
        self.area = area
        super(CacheObjectCreatedEvent, self).__init__(object)

class CacheObjectModifiedEvent(ObjectModifiedEvent):
    implements(ICacheObjectModifiedEvent)
    def __init__(self, object, area):
        self.area = area
        super(ObjectModifiedEvent, self).__init__(object)