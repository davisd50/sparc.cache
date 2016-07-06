import json
import requests
from zope.component.factory import Factory
from zope.event import notify
from zope.interface import implements
from sparc.cache.events import CacheObjectCreatedEvent, CacheObjectModifiedEvent
from sparc.cache import ICachableSource
from sparc.cache import ITrimmableCacheArea
from sparc.db.splunk.kvstore import current_kv_names

from sparc.logging import logging
logger = logging.getLogger(__name__)

class CacheAreaForSplunkKV(object):
    """An area where cached information can be stored persistently."""
    implements(ITrimmableCacheArea)

    def __init__(self, mapper, schema, sci, kv_id):
        """Object initializer

        Args:
            mapper: Object providing sparc.cache.ICachedItemMapper that will
                    convert ICachableItem instances into ICachedItem instances.
            schema: Object providing sparc.db.splunk.ISplunkKVCollectionSchema.
            sci: sparc.db.splunk.ISplunkConnectionInfo instance to provide
                 connection information for Splunk indexing server
            kv_id: Object providing sparc.db.splunk.ISPlunkKVCollectionIdentifier
        """
        self.mapper = mapper
        self.schema = schema
        self.sci = sci
        self.kv_id = kv_id
        self.collname = kv_id.collection
        self.appname = kv_id.application
        self.username = kv_id.username
        self.url = "".join(['https://',sci['host'],':',sci['port'],
                                    '/servicesNS/',self.username,'/',
                                                        self.appname,'/'])
        self.auth = (self.sci['username'], self.sci['password'], )

    def current_kv_names(self):
        """Return set of string names of current available Splunk KV collections"""
        return current_kv_names(self.sci, self.username, self.appname)
    
    def _data(self, CachedItem):
        data = {k:getattr(CachedItem, k) for k in self.mapper.mapper}
        data['_key'] = CachedItem.getId()
        return data
    
    def _add(self, CachedItem):
        r = requests.post(self.url+"storage/collections/data/"+self.collname,
                        auth=self.auth,
                        headers = {'Content-Type': 'application/json'},
                        data=json.dumps(self._data(CachedItem)), 
                        verify=False)
        r.raise_for_status()
    
    def _update(self, CachedItem):
        r = requests.post(self.url+"storage/collections/data/"+self.collname+'/'+CachedItem.getId(),
                        auth=self.auth,
                        headers = {'Content-Type': 'application/json'},
                        data=json.dumps(self._data(CachedItem)), 
                        verify=False)
        r.raise_for_status()
    
    def _delete(self, id_):
        if not id_:
            raise ValueError("Expected valid id for deletion")
        r = requests.delete(self.url+"storage/collections/data/"+self.collname+'/'+str(id_),
                        auth=self.auth,
                        verify=False)
        r.raise_for_status()

    def _all_ids(self):
        r = requests.get(self.url+"storage/collections/data/"+self.collname,
                        auth=self.auth,
                        headers = {'Content-Type': 'application/json'},
                        params={'output_type': 'json', 'fields':'id'}, 
                        verify=False)
        r.raise_for_status()
        data = set(map(lambda d: str(d['id']), r.json()))
        return data

    #ICacheArea
    def get(self, CachableItem):
        """Returns current ICachedItem for ICachableItem or None if not cached"""
        cached_item = self.mapper.get(CachableItem)
        r = requests.get(self.url+"storage/collections/data/"+\
                                        self.collname+'/'+cached_item.getId(),
                            auth=self.auth,
                            data={'output_mode': 'json'},
                            verify=False)
        if r.ok:
            # we need to update the object with the values found in the cache area
            data = r.json()
            for name in self.mapper.mapper:
                setattr(cached_item, name, data[name])
            return cached_item
        return None
        

    def isDirty(self, CachableItem):
        """True if cached information requires update for ICachableItem"""
        _cachedItem = self.get(CachableItem)
        if not _cachedItem:
            return True
        _newCacheItem = self.mapper.get(CachableItem)
        return False if _cachedItem == _newCacheItem else True

    def cache(self, CachableItem):
        """Updates caches area with latest item information returning
           ICachedItem if cache updates were required.

           Issues ICacheObjectCreatedEvent, and ICacheObjectModifiedEvent for
           ICacheArea/ICachableItem combo.
        """
        _cachedItem = self.get(CachableItem)
        if not _cachedItem:
            _cachedItem = self.mapper.get(CachableItem)
            self._add(_cachedItem)
            logger.debug("new cachable item added to Splunk KV cache area {id: %s, type: %s}", str(_cachedItem.getId()), str(_cachedItem.__class__))
            notify(CacheObjectCreatedEvent(_cachedItem, self))
            return _cachedItem
        else:
            _newCacheItem = self.mapper.get(CachableItem)
            if _cachedItem != _newCacheItem:
                logger.debug("Cachable item modified in Splunk KV cache area {id: %s, type: %s}", str(_newCacheItem.getId()), str(_newCacheItem.__class__))
                self._update(_newCacheItem)
                notify(CacheObjectModifiedEvent(_newCacheItem, self))
                return _newCacheItem
        return None

    def import_source(self, CachableSource):
        """Updates cache area and returns number of items updated with all
           available entries in ICachableSource
        """
        _count = 0
        self._import_source_items_id_list = set() # used to help speed up trim()
        for item in CachableSource.items():
            self._import_source_items_id_list.add(item.getId())
            if self.cache(item):
                _count += 1
        return _count

    def reset(self):
        """Deletes all entries in the cache area"""
        if self.collname not in self.current_kv_names():
            return # nothing to do
        # we'll simply delete the entire collection and then re-create it.
        r = requests.delete(self.url+"storage/collections/data/"+self.collname,
                        auth=self.auth,
                        verify=False)
        r.raise_for_status()
        self.initialize()
        
    def initialize(self):
        """Instantiates the cache area to be ready for updates"""
        if self.collname not in self.current_kv_names():
            r = requests.post(self.url+"storage/collections/config",
                            auth=self.auth,
                            headers = {'content-type': 'application/json'},
                            data={'name': self.collname},
                            verify=False)
            r.raise_for_status()
        # initialize schema
        re = requests.post(self.url+"storage/collections/config/"+self.collname,
                            auth=self.auth,
                            headers = {'content-type': 'application/json'},
                            data=self.schema,
                            verify=False)
        re.raise_for_status()
        logger.info("initialized Splunk Key Value Collection %s with schema %s"\
                        % (self.collname, str(self.schema)))
        if self.collname not in self.current_kv_names():
            raise EnvironmentError('expected %s in list of kv collections %s' % (self.collname, str(self.current_kv_names())))
    
    #ITrimmableCacheArea
    def trim(self, source):
        if not ICachableSource.providedBy(source):
            #we'll fake a partial ICachableSource for use with import_source()
            source_type = type('FakeCachableSource', (object,), {})
            _source = source #re-assign due to closure issue with source re-assignment below
            source_type.items = lambda self: _source
            source = source_type()
        updated = self.import_source(source)
        diff = self._all_ids() - self._import_source_items_id_list
        map(self._delete, diff)
        return (updated, len(diff), )
            

cacheAreaForSplunkKVFactory = Factory(CacheAreaForSplunkKV)
