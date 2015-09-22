from zope.interface import Interface, implements
from zope.component.factory import IFactory
from zope.component import adapts, queryAdapter
from sqlalchemy.orm import Session
from datetime import date
import sqlalchemy.orm
import sqlalchemy.ext.declarative

from sparc.common import ConfigurationRequired
from sparc.cache import ICacheArea, ICachableSource, ICachableItem, ICachedItem
from sparc.cache import ICachedItemMapper, IManagedCachedItemMapperAttribute, IManagedCachedItemMapperAttributeKeyWrapper
from sparc.db import ISqlAlchemySession

import sparc.common.log
import logging
logger = logging.getLogger('sparc.cache.sql')

class ICachedItemMapperSqlCompatible(Interface):
    """Marker interface for ICachedItemMapper implementations that indicates compatibility with SQL-based ICacheArea"""

class SqlObjectMapperMixin(object):
    """Base class for ICachedItemMapper implementations
    
    This is a helper class that can be inherited by implementation to implement
    ICachedItemMapper.  This class implements a get method that will automatically
    convert DATE, INT, and UNICODE type fields into the corresponding Python
    Types.
    
    This class has a dependency on component configuration.
    """
    
    implements(ICachedItemMapper, ICachedItemMapperSqlCompatible)
    adapts(ICachableSource, IFactory) #subscription
    mapper = {}
    
    @ConfigurationRequired
    def __init__(self, myCachableSource, myCachedItemFactory):
        """
        Args:
            myCachableSource: 
        """
        self.myCachableSource = myCachableSource
        self.myCachedItemFactory = myCachedItemFactory
    
    def key(self):
        for _key, _value in self.mapper.iteritems():
            if _value == self.myCachableSource.key():
                return _key
        raise LookupError("expected to find matching cache key for given source key via map lookup")
    
    def factory(self):
        return self.myCachedItemFactory()
    
    def get(self, sourceItem):
        _cachedItem = self.factory()
        #_sqlInspecter = sqlalchemy.inspection.inspect(_cachedItem)
        for _cachedAttrKeyName in _cachedItem.__class__.__dict__.keys(): # iterate the actual cache object to make sure we don't miss any attributes
            if not isinstance(_cachedItem.__class__.__dict__[_cachedAttrKeyName], sqlalchemy.orm.attributes.InstrumentedAttribute): # these are the column assignments
                continue
            if _cachedAttrKeyName not in self.mapper:
                raise LookupError("expected to find cached object attribute in mapper keys: %s", _cachedAttrKeyName)
            
            _sourceAttrKey = self.mapper[_cachedAttrKeyName]
            #if queryAdapter(_sourceAttrKey, IManagedCachedItemMapperAttributeKeyWrapper):
            if IManagedCachedItemMapperAttributeKeyWrapper.providedBy(_sourceAttrKey):
                _sourceAttrValue = sourceItem.attributes[_sourceAttrKey()]
            else:
                _sourceAttrValue = sourceItem.attributes[_sourceAttrKey]
            _cachedAttrValue_new = None
            _sql_field_type_name = str(_cachedItem.__table__.c[_cachedAttrKeyName].type)
            
            if queryAdapter(_sourceAttrKey, IManagedCachedItemMapperAttribute): # MANAGED ATTRIBUTES
                _cachedAttrValue_new = None if not _sourceAttrValue else IManagedCachedItemMapperAttribute(_sourceAttrKey).manage(_sourceAttrValue)

            elif 'INT' in _sql_field_type_name.upper():
                try:
                    _cachedAttrValue_new = int(_sourceAttrValue)
                except ValueError:
                    _cachedAttrValue_new = None
            else:
                _cachedAttrValue_new = _sourceAttrValue.decode('utf8', 'replace') if _sourceAttrValue else None
            
            _cachedItem.__dict__[_cachedAttrKeyName] = _cachedAttrValue_new
        logger.debug("generated cached item from source, values: %s", str(_cachedItem.getId()))
        return _cachedItem
    
    def check(self, sourceItem):
        try:
            self.get(sourceItem) # fails if a required field can not be found in source
        except LookupError as e:
            logger.debug("Source item failed check due to error: %s", str(e))
            return False
        return True

class SqlObjectCacheArea(object):
    """Adapter implementation for cachable storage into a SQLAlchemy DB backend
    
    You MUST indicate that your SQL Alchemy Session objects provide the
    related marker interfaces prior to calling this adapter (see usage example
    in sql.txt)
    
    Interface implementation requirements:
        To use this class, several class dependencies must be met.  The following
        break-down should help you better understand the Interface dependencies
        - ICacheArea (this class)
          - ISqlAlchemySession (marker interface, applied to SQLAlchemy session object)
          - ICachedItemMapper
            - ICachableSource
            - ICachedItem (indirect...required for __init__)
          - ICachableItem (needed via method calls)
        
        
    """
    implements(ICacheArea)
    adapts(ISqlAlchemySession, ICachedItemMapper)
    
    def __init__(self, SqlAlchemySession, CachedItemMapper):
        """Object initialization
        """
        self.session = SqlAlchemySession
        self.mapper = CachedItemMapper
        
        if not isinstance(SqlAlchemySession, Session):
            raise TypeError("expected SQLAlchmey_session to be an instance of:"
                            + " sqlalchemy.orm.Session")
        assert SqlAlchemySession.bind, "expected SQLAlchmey_session to be "\
                            + "bound to Engine"
    
    def get(self, CachableItem):
        """Returns current ICachedItem for ICachableItem
        
        Args:
            CachableItem: ICachableItem, used as a reference to find a cached version
        
        Returns: ICachedItem or None, if CachableItem has not been cached
        """
        return self.session.\
                        query(self.mapper.factory().__class__).\
                        filter(self.mapper.factory().__class__.__dict__[self.mapper.key()]==CachableItem.getId()).\
                        first()
    
    def isDirty(self, CachableItem):
        """True if cached information requires update for ICachableItem
        
        Args:
            CachableItem: ICachableItem, used as a reference to find a cached version
        
        Returns: True if CachableItem requires a cache update
        """
        # we'll create a new ICachedItem from the current data and compare it to
        # ICachedItem we get from the DB
        _cachedItem = self.get(CachableItem)
        if not _cachedItem:
            return True
        _newCacheItem = self.mapper.get(CachableItem)
        return False if _cachedItem == _newCacheItem else True
        
    def cache(self, CachableItem):
        """Updates cache area with latest information
        """
        if self.isDirty(CachableItem):
            _dirtyCachedItem = self.mapper.get(CachableItem)
            logger.debug("cached item required sql cache area update {id: %s, type: %s}", str(_dirtyCachedItem.getId()), str(_dirtyCachedItem.__class__))
            return self.session.merge(_dirtyCachedItem)
        return False
    
    def import_source(self, CachableSource):
        """Updates cache area and returns number of items updated with all available entries in ICachableSource"""
        _count = 0
        for item in CachableSource.items():
            if self.cache(item):
                _count += 1
        return _count
        
    def commit(self):
        self.session.commit()
        
    def rollback(self):
        self.session.rollback()
    
    def reset(self, SqlAlchemyBase):
        """Deletes all entries in the cache area"""
        SqlAlchemyBase.metadata.drop_all(self.session.bind)
        self.initialize()
        
    def initialize(self, SqlAlchemyBase):
        """Instantiates the cache area to be ready for updates"""
        SqlAlchemyBase.metadata.create_all(self.session.bind)
        
