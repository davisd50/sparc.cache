from zope.interface import Interface, Attribute

class ICachedItemMapper(Interface):
    """Manage attribute mappings between ICachableItem and ICachedItem
    
    For simple maps that contains only strings and integers, map  is simply a key value
    pair of the mapped items.  If the ICachableItem contains complex attributes, such
    as a date, then they should be object adaptable to IManagedCachedItemMapperAttribute
    """
    
    map = Attribute("Dictionary map of ICachedItem attribute keys to equivalent ICachableItem attribute keys.")
        
    def key():
        """Returns string identifier of ICachedItem attribute that represents unique item entries (e.g. primary key field name)"""
    
    def factory():
        """Returns instance of ICachedItem with unassigned attributes"""
    
    def get(ICachableItem):
        """Returns ICachedItem representing ICachableItem"""
    
    def check(ICachableItem):
        """True is returned if ICachableItem can be mapped into a ICachedItem"""

class IManagedCachedItemMapperAttributeKeyWrapper(Interface):
    """Key name wrapper for a managed attribute
    
    We use this so that we can apply an interface onto, what would normally be
    a python string.  We wrap that string within this interface so that we
    ca use it for adapter lookups.
    """
    def __call__():
        """Returns the key name string of a managed attribute"""

class IManagedCachedItemMapperAttribute(Interface):
    """An attribute whose value needs to be managed before assignment to a ICachedItem (i.e. a date field)"""
    def manage(value):
        """Returns a cachable attribute value"""
        
class ICachableItem(Interface):
    """An item who's information can be cached."""
    
    attributes = Attribute("Dictionary map of ICachableItem attributes and related values")
    key = Attribute("String that identifies the item's unique key attribute whose value will be returned by getId()")
    
    def getId():
        """Return item unique identifier attribute value"""
    
    def validate():
        """Check item's validity"""

class ICachableSource(Interface):
    """A source of data that can be cached as ICachableItem in a ICacheArea."""
    
    def key():
        """Returns string identifier key that marks unique item entries (e.g. primary key field name)"""
    
    def items():
        """Returns an iterable of available ICachableItem in the ICachableSource"""
    
    def getById(Id):
        """Returns ICachableItem that matches Id or None if not found"""
    
    def first():
        """Returns the first ICachableItem available in the ICachableSource or None"""

class ICachedItem(Interface):
    """A cached item."""
    
    def getId():
        """Return item unique identifier"""
    
    def __eq__(instance):
        """Returns True if current object should be considered equivalent to instance"""
    
    def __ne__(instance):
        """Returns True if current object should not be considered equivalent to instance"""

class IAgeableCachedItem(ICachedItem):
    """A cached item that has an age"""
    def birth():
        """Python datetime of cached item's creation"""
    def age():
        """Python timedelta of cached item's current age"""
    def expiration():
        """Python datetime of when cached item should be considered invalid"""
    def expiration_age():
        """Python timedelta of when cached item should be considered invalid"""
    def expired():
        """True indicates the cached item is expired"""

class ICacheArea(Interface):
    """An area where cached information can be stored persistently."""
        
    def get(ICachableItem):
        """Returns current ICachedItem for ICachableItem or None if not cached"""
    
    def isDirty(ICachableItem):
        """True if cached information requires update for ICachableItem"""
    
    def cache(ICachableItem):
        """Updates caches area with latest item information returning ICachedItem if cache updates were required"""
    
    def import_source(ICachableSource):
        """Updates cache area and returns number of items updated with all available entries in ICachableSource"""
    
    def commit():
        """Commits changes for transaction capable ICacheAreas"""
    
    def rollback():
        """Rollback changes for transaction capable ICacheAreas"""
    
    def reset():
        """Deletes all entries in the cache area"""
        
    def initialize():
        """Instantiates the cache area to be ready for updates"""

class ILocatableCacheArea(ICacheArea):
    """
    Same as ICacheArea except zope.location.ILocation must be provided by
    ICachableItem parameters for method calls.  This type of cache will store
    items in a hierarchy (e.g. children have parents).
    """