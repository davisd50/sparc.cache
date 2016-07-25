from zope import component
from zope import interface
from sparc.cache.events import CacheObjectCreatedEvent, CacheObjectModifiedEvent
from zope.container.interfaces import IContainer
from zope.event import notify
from sparc.cache import ICacheArea


class IdentifiedPersistentObjectCacheAreaForZopeContainer(object):
    interface.implements(ICacheArea)
    component.adapts(IContainer)
    
    def __init__(self, context):
        self.context = context
    
    def mapper(self, ICachableItem):
        return component.createObject(u'sparc.cache.simple_item_mapper',
                                                        'id', ICachableItem)
    
    def get(self, ICachableItem):
        """Returns current ICachedItem for ICachableItem or None if not cached"""
        return self.context.get(ICachableItem.getId(), None)
    
    def isDirty(self, ICachableItem):
        """True if cached information requires update for ICachableItem"""
        mapper = self.mapper(ICachableItem)
        if ICachableItem.getId() not in self.context:
            return True
        return False if \
                mapper.get(ICachableItem) == \
                                self.context[ICachableItem.getId()] else True
    
    def cache(self, ICachableItem):
        """Updates caches area with latest item information returning 
           ICachedItem if cache updates were required.
           
           Issues ICacheObjectCreatedEvent, and ICacheObjectModifiedEvent for 
           ICacheArea/ICachableItem combo.
        """
        mapper = self.mapper(ICachableItem)
        if not self.get(ICachableItem):
            new = mapper.get(ICachableItem)
            self.context[unicode(new.getId())] = new
            notify(CacheObjectCreatedEvent(new, self))
            return new
        
        if self.isDirty(ICachableItem):
            updated = mapper.get(ICachableItem)
            del self.context[unicode(ICachableItem.getId())] # not sure why, but direct re-assignment is not allowed
            self.context[unicode(ICachableItem.getId())] = updated
            notify(CacheObjectModifiedEvent(updated, self))
            return updated
    
    def import_source(self, ICachableSource):
        """Updates cache area and returns number of items updated with all 
           available entries in ICachableSource
        """
        _count = 0
        for item in ICachableSource.items():
            if self.cache(item):
                _count += 1
        return _count
    
    def reset(self):
        """Deletes all entries in the cache area"""
        for k in self.context.keys():
            del self.context[k]
    
    def initialize(self):
        """Instantiates the cache area to be ready for updates"""
        # nothing to do here