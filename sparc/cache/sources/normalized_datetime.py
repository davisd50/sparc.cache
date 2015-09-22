from datetime import datetime
from zope.interface import implements
from zope.component import adapts
from zope.component.factory import Factory

from sparc.cache import IManagedCachedItemMapperAttribute, IManagedCachedItemMapperAttributeKeyWrapper
from sparc.cache.sources import INormalizedDateTime
from sparc.cache.item import cachableItemMixin
from sparc.cache.sql import SqlObjectMapperMixin

class normalizedFieldNameSqlObjectMapperMixin(SqlObjectMapperMixin):
    """Base class for normalized field name ICachedItemMapper implementations
    """
    
    def __init__(self, myCachableSource, myCachedItemFactory):
        _new_mapper = {}
        for mapper, attribute in self.mapper.iteritems():
            if IManagedCachedItemMapperAttributeKeyWrapper.providedBy(attribute): # managed attributes
                attribute.key = normalizedFieldNameCachableItemMixin.normalize(attribute.key)
                _new_mapper[mapper] = attribute
            else:
                _new_mapper[mapper] = normalizedFieldNameCachableItemMixin.normalize(attribute) # unmanaged attribute
        self.mapper = _new_mapper
        super(normalizedFieldNameSqlObjectMapperMixin, self).__init__(myCachableSource, myCachedItemFactory)

class normalizedFieldNameCachableItemMixin(cachableItemMixin):
    """Base class for ICachableItem implementations for data requiring normalized field names.
    
    This class provides extra functionality to deal with minor differences
    in attribute names when different variations of the string should be
    considered equal.  The following strings should be considered equal:
     - Entry #
     - ENTRY #
     - Entry#
    """
    
    def __init__(self, key, attributes):
        
        """Object initialization
        
        Args:
            key: String name of an attributes key that represents the unique identify of the request
            attributes: Dictionary whose keys match the string values of the request attribute's names and values correspond the the request attribute values
        """
        self._attributes_normalized = {}
        self._set_attributes(attributes if attributes else {})
        self._key_normalized = ''
        self._set_key(key)
    
    def _set_attributes(self, attributes):
        self._attributes_raw = attributes
        for key, value in attributes.iteritems():
            self._attributes_normalized[self.normalize(key)] = value
    
    def _get_attributes(self):
        return self._attributes_normalized
    
    def _set_key(self, key):
        self._key_raw = key
        self._key_normalized = self.normalize(key)
    
    def _get_key(self):
        return self._key_normalized
    
    @classmethod
    def normalize(cls, name):
        """Return string in all lower case with spaces and question marks removed"""
        name = name.lower() # lower-case
        for _replace in [' ','-','(',')','?']:
            name = name.replace(_replace,'')
        return name
    
    attributes = property(_get_attributes, _set_attributes)
    key = property(_get_key, _set_key)

class normalizedDateTime(object):
    implements(INormalizedDateTime, IManagedCachedItemMapperAttributeKeyWrapper)
    def __init__(self, key):
        self.key = key
    
    def __call__(self):
        return self.key

normalizedDateTimeFactory = Factory(normalizedDateTime, 'normalizedDateTime', 'generates empty INormalizedDateTime objects')

class normalizedDateTimeResolver(object):
    implements(IManagedCachedItemMapperAttribute)
    adapts(INormalizedDateTime)
    
    def __init__(self, context):
        self.context = context
    
    def manage(self, dateTimeString):
        """Return a Python datetime object based on the dateTimeString
        
        This will handle date times in the following formats:
            YYYY/MM/DD HH:MM:SS
            2014/11/05 21:47:28
            2014/11/5 21:47:28
            11/05/2014
            11/5/2014
            11/05/2014 16:28:00
            11/05/2014 16:28
            11/5/2014 16:28:00
            11/5/2014 16:28
        It can also handle these formats when using a - instead of a / for a 
        date separator.
        """
        dateTime = None
        dateTimeString = dateTimeString.replace('-', '/')
        
        _date_time_split = dateTimeString.split(' ') # [0] = date, [1] = time (if exists)
        _date = _date_time_split[0]
        _time = '00:00:00' # default
        if len(_date_time_split) > 1:
            _time = _date_time_split[1]
        
        if dateTimeString.find('/') == 4: # YYYY/MM/DD...
            dateList = _date.split('/') + _time.split(':')
            dateTime = datetime(*map(lambda x: int(x), dateList))
        elif 1 <= dateTimeString.find('/') <= 2: # MM/DD/YYYY or M/D?/YYYY
            _date_split = _date.split('/')
            dateList = [_date_split[2], _date_split[0], _date_split[1]] + _time.split(':')
            dateTime = datetime(*map(lambda x: int(x), dateList))
        if not dateTime:
            raise ValueError("unable to manage unsupported string format: %s"%(dateTimeString))
        
        return dateTime
