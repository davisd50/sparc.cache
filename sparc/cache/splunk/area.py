import json
from zope.component import adapts
from zope.event import notify
from zope.interface import implements
from sparc.cache.events import CacheObjectCreatedEvent, CacheObjectModifiedEvent
from sparc.cache import ICachableSource
from sparc.cache import ITrimmableCacheArea
import sparc.cache
import sparc.db.splunk
import sparc.utils.requests
from sparc.db.splunk.kvstore import current_kv_names

from sparc.logging import logging
logger = logging.getLogger(__name__)

class CacheAreaForSplunkKV(object):
    """An area where cached information can be stored persistently."""
    implements(ITrimmableCacheArea)
    adapts(sparc.cache.ICachedItemMapper,
           sparc.db.splunk.ISplunkKVCollectionSchema,
           sparc.db.splunk.ISplunkConnectionInfo,
           sparc.db.splunk.ISPlunkKVCollectionIdentifier,
           sparc.utils.requests.IRequest)

    def __init__(self, mapper, schema, sci, kv_id, request):
        """Object initializer

        Args:
            mapper: Object providing sparc.cache.ICachedItemMapper that will
                    convert ICachableItem instances into ICachedItem instances.
            schema: Object providing sparc.db.splunk.ISplunkKVCollectionSchema.
            sci: sparc.db.splunk.ISplunkConnectionInfo instance to provide
                 connection information for Splunk indexing server
            kv_id: Object providing sparc.db.splunk.ISPlunkKVCollectionIdentifier
            request: Object providing sparc.utils.requests.IRequest
        """
        self.gooble_request_warnings = False
        self.mapper = mapper
        self.schema = schema
        self.sci = sci
        self.kv_id = kv_id
        self._request = request
        self._request.req_kwargs['auth'] = (self.sci['username'], self.sci['password'],)
        self.collname = kv_id.collection
        self.appname = kv_id.application
        self.username = kv_id.username
        self.url = "".join(['https://',sci['host'],':',sci['port'],
                                    '/servicesNS/',self.username,'/',
                                                        self.appname,'/'])

    def current_kv_names(self):
        """Return set of string names of current available Splunk KV collections"""
        return current_kv_names(self.sci, self.username, self.appname, request=self._request)
    
    def request(self, *args, **kwargs):
        return self._request.request(*args, **kwargs)

    def _data(self, CachedItem):
        data = {k:getattr(CachedItem, k) for k in self.mapper.mapper}
        data['_key'] = CachedItem.getId()
        return data
    
    def _add(self, CachedItem):
        r = self.request('post',
                         self.url+"storage/collections/data/"+self.collname, 
                         headers={'Content-Type': 'application/json'}, 
                         data=json.dumps(self._data(CachedItem)))
        r.raise_for_status()
    
    def _update(self, CachedItem):
        r = self.request('post',
            self.url+"storage/collections/data/"+self.collname+'/'+CachedItem.getId(),
            headers={'Content-Type': 'application/json'}, 
            data=json.dumps(self._data(CachedItem)))
        r.raise_for_status()
    
    def _delete(self, id_):
        if not id_:
            raise ValueError("Expected valid id for deletion")
        r = self.request('delete', 
                self.url+"storage/collections/data/"+self.collname+'/'+str(id_))
        r.raise_for_status()

    def _all_ids(self):
        r = self.request('get',
                         self.url+"storage/collections/data/"+self.collname,
                         headers={'Content-Type': 'application/json'}, 
                         params={'output_type': 'json', 'fields':'id'})
        r.raise_for_status()
        data = set(map(lambda d: str(d['id']), r.json()))
        return data

    #ICacheArea
    def get(self, CachableItem):
        """Returns current ICachedItem for ICachableItem or None if not cached"""
        cached_item = self.mapper.get(CachableItem)
        r = self.request('get',
            self.url+"storage/collections/data/"+self.collname+'/'+cached_item.getId(),
            data={'output_mode': 'json'})
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
        r = self.request('delete',
                         self.url+"storage/collections/data/"+self.collname)
        r.raise_for_status()
        self.initialize()
        
    def initialize(self):
        """Instantiates the cache area to be ready for updates"""
        if self.collname not in self.current_kv_names():
            r = self.request('post',
                             self.url+"storage/collections/config",
                             headers={'content-type': 'application/json'},
                             data={'name': self.collname})
            r.raise_for_status()
        # initialize schema
        re = self.request('post',
                          self.url+"storage/collections/config/"+self.collname,
                          headers = {'content-type': 'application/json'},
                          data=self.schema)
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

