import zope.component
from zope.component.factory import Factory
import zope.interface
import sparc.cache

class CachableSourceFromIterable(object):
    zope.interface.implements(sparc.cache.ICachableSource)
    
    def __init__(self, iterable):
        self._key = None
        self._items = []
        self._index = {}
        for item in iterable:
            if not self._key:
                self._key = item.key
            self._items.append(item)
            self._index[item.attributes[self.key()]] = len(self._items) - 1
    
    def key(self):
        return self._key
    
    def items(self):
        return self._items
    
    def getById(self, Id):
        if Id not in self._index:
            return None
        index = self._index[Id]
        return self._items[index]
    
    def first(self):
        if not self._items: return None
        return self._items[0]

cachableSourceFromIterableFactory = Factory(CachableSourceFromIterable)