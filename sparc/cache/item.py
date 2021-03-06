import datetime
import inspect
from zope.interface import alsoProvides
from zope.interface import implements
from zope.component import subscribers
from zope.component.interfaces import IFactory
from zope.component.factory import Factory
from zope.schema import getFieldNames
from sparc.cache import ICachableItem, ICachedItem, IAgeableCachedItem, ICachedItemMapper

from sparc.logging import logging
logger = logging.getLogger(__name__)

def schema_map(schema):
    """Return a valid ICachedItemMapper.map for schema"""
    mapper = {}
    for name in getFieldNames(schema):
        mapper[name] = name
    return mapper

class CachedItemMapperFactory(object):
    implements(IFactory)
    
    title = u"Create object with ICachedItemMapper from ICachableSource, CachedItemFactory"
    description = u"Allows for easy ICachedItemMapper generation"
    
    def __call__(self, CachableSource, CachedItemFactory):
        item = CachableSource.first()
        if not item:
            raise ValueError("expected CachableSource to be able to generate at least 1 item.")
        for mapper in subscribers((CachableSource,CachedItemFactory,), ICachedItemMapper):
            logger.debug("testing mapper/cachedItem combination: %s, %s", str(mapper), str(CachedItemFactory))
            if mapper.check(item):
                logger.debug("found valid ICachedItemMapper %s", str(mapper))
                return mapper
            logger.debug("skipping CachedItemMapper %s because item failed mapper validation check", str(mapper))
        raise LookupError("unable to find subscribed ICachedItemMapper for given source and factory: %s, %s", str(CachableSource). str(CachedItemFactory))
    
    def getInterfaces(self):
        return [ICachedItemMapper]

class cachableItemMixin(object):
    """Base class for ICachableItem implementations
    """
    implements(ICachableItem)
    
    def __init__(self, key, attributes):
        
        """Object initialization
        
        Args:
            key: String name of an attributes key that represents the unique identify of the request
            attributes: Dictionary whose keys match the string values of the request attribute's names and values correspond the the request attribute values
        """
        self.key = key
        self.attributes = attributes
    
    def getId(self):
        return self.attributes[self.key]
    
    def validate(self):
        if not self.attributes.has_key(self.key):
            raise KeyError("expected item's attributes to have entry for key field: %s in keys: %s", self.key, str(self.attributes.keys()))
        if not self.attributes[self.key]:
            raise ValueError("expected item's key attribute to have a non-empty value")
        logger.debug("item passed validation: %s", str(self.getId()))
simpleCachableItemFactory = Factory(cachableItemMixin)

class CachableItemFromSchema(cachableItemMixin):
    """Create a ICachableItem from a zope schema interface
    """
    implements(ICachableItem)
    def __init__(self, key, schema, object=None):
        super(CachableItemFromSchema, self).__init__(key, 
                            {k:None for k in getFieldNames(schema)})
        if object:
            for name in getFieldNames(schema):
                self.attributes[name] = getattr(object, name)
cachableItemFromSchemaFactory = Factory(CachableItemFromSchema)

class cachedItemMixin(object):
    """Base class for ICachedItem implementations
    """
    implements(ICachedItem)
    
    _key = 'Must be defined by implementers'
    # implementers can place a list of Interfaces here that will used when checking
    # equivalence.  Otherwise all attributes are checked minus getId() and those 
    # starting with '_'
    _eq_checked_interfaces = [] 
    
    def getId(self):
        return getattr(self, self._key)
    
    def __eq__(self, instance):
        attributes = []
        if self._eq_checked_interfaces:
            for iface in self._eq_checked_interfaces:
                for name in iface:
                    attributes.append(name)
        else:
            for name, value in inspect.getmembers(self):
                if name.startswith("_") or name in ['getId']:
                    continue
                attributes.append(name)
        for name in attributes:
            if not hasattr(instance, name):
                return False
            if getattr(self, name) != getattr(instance, name):
                return False
        return True
   
    def __ne__(self, instance):
        return not self.__eq__(instance)

class ageableCacheItemMixin(cachedItemMixin):
    """Base class for IAgeableCachedItem implementations
    
    Implementers can set:
        self._birth: [optional].  Python datetime of cache item creation
        self._expiration: [do not set if self._expiration_age is set].  Python
                          datetime of when cache item is no longer valid
        self._expiration_age: [do not set if self._expiration is set].  Python
                              timedelta of maximum item age before it is considered
                              invalid.
        
        If the parameters above are not set, these defaults will be assigned:
        
        _birth: defaults to now
        _expiration|_expiration_age: defaults to datetime.MAXYEAR
    """
    implements(IAgeableCachedItem)
    
    def __init__(self):
        if not hasattr(self, '_birth'):
            self._birth = datetime.datetime.now()
        if hasattr(self, '_expiration'):
            self._expiration_age = self._expiration - self._birth
        elif hasattr(self, '_expiration_age'):
            self._expiration = self._birth + self._expiration_age
        else:
            self._expiration = datetime.datetime(datetime.MAXYEAR, 12, 31)
            self._expiration_age = self._expiration - self._birth
            
    def birth(self):
        return self._birth
    def age(self):
        return datetime.datetime.now() - self._birth
    def expiration(self):
        return self._expiration
    def expiration_age(self):
        return self._expiration_age
    def expired(self):
        return datetime.datetime.now > self._expiration

class SimpleItemMapper(object):
    """A simple attribute item mapper
    
    A very simple implementation that will generate on-the-fly ICachedItem
    objects with one-to-one mappings to ICachableItem.attributes key/value.
    """
    implements(ICachedItemMapper)
    
    def __init__(self, key, CacheableItem, filter=None):
        """Init
        
        Args:
            key: String name of CacheableItem.attributes key that should be 
                 considered the unique primary key identifier for the object.
            CacheableItem: instance of sparc.cache.ICachableItem whose
                           attributes have the required keys populated
            filter: Callable taking two arguments.  The first argument is the
                    attribute name, the second is the ICachableItem value of
                    that attribute.  The return value should be what will be
                    assigned to the related attribute on the ICacheItem
        """
        self._key = key
        self.mapper = {k:k for k in CacheableItem.attributes}
        self.filter = filter if filter else lambda x,y:y
    
    #ICachedItemMapper
    def key(self):
        return self._key
    
    def factory(self):
        #base = cachedItemMixin()
        #base._key = self.key()
        ci = type('SimpleItemMapperCachedItem', (cachedItemMixin,), {key:None for key in self.mapper.keys()})()
        ci._key = self.key()
        alsoProvides(ci, ICachedItem)
        return ci
    
    def get(self, CachableItem):
        ci = self.factory()
        for name in self.mapper:
            setattr(ci, name, self.filter(name, CachableItem.attributes[name]))
        return ci
    
    def check(self, CachableItem):
        for name in self.mapper:
            if name not in CachableItem.attributes:
                return False
        return True
simpleItemMapperFactory = Factory(SimpleItemMapper)
    