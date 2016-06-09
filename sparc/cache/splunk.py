import json
import requests
import xml.etree.ElementTree as ET
from zope.component.factory import Factory
from zope.event import notify
from zope.interface import implements
from sparc.cache.events import CacheObjectCreatedEvent, CacheObjectModifiedEvent
from interfaces import ICacheArea

from sparc.logging import logging
logger = logging.getLogger(__name__)

class CacheAreaForSplunkKV(object):
    """An area where cached information can be stored persistently."""
    implements(ICacheArea)

    def __init__(self, mapper, schema, sci, collname, appname, username='nobody'):
        """Object initializer

        Args:
            mapper: Object providing sparc.cache.ICachedItemMapper that will
                    convert ICachableItem instances into ICachedItem instances.
            schema: Object providing sparc.db.splunk.ISplunkKVCollectionSchema.
            sci: sparc.db.splunk.ISplunkConnectionInfo instance to provide
                 connecton information for Splunk indexing server
            collname: String KV collection name
            appname: String name of Splunk application to host key value store
            username: username to host key value store
        """
        self.mapper = mapper
        self.schema = schema
        self.sci = sci
        self.collname = collname
        self.appname = appname
        self.username = username
        self.url = "".join(['https://',sci['host'],':',sci['port'],
                                    '/servicesNS/',username,'/',appname,'/'])
        self.auth = (self.sci['username'], self.sci['password'], )

    def current_kv_names(self):
        """Return set of string names of current available Splunk KV collections"""
        _return = set()
        re = requests.get(self.url+"storage/collections/config",auth=self.auth, verify=False)
        root = ET.fromstring(re.text)
        for entry in root.findall('./{http://www.w3.org/2005/Atom}entry'):
            name = entry.find('{http://www.w3.org/2005/Atom}title').text
            if not name:
                raise ValueError('unexpectedly found empty collection title')
            _return.add(name)
        return _return
    
    def _add(self, CachedItem):
        data = {k:getattr(CachedItem, k) for k in self.schema}
        data['_key'] = CachedItem.getId()
        r = requests.post(self.url+"storage/collections/data/"+self.collname,
                        auth=self.auth,
                        headers = {'content-type': 'application/json'},
                        data=json.dumps(data), 
                        verify=False)
    
    def _update(self, CachedItem):
        data = {k:getattr(CachedItem, k) for k in self.schema}
        data['_key'] = CachedItem.getId()
        r = requests.post(self.url+"storage/collections/data/"+self.collname+'/'+CachedItem.getId(),
                        auth=self.auth,
                        headers = {'content-type': 'application/json'},
                        data=json.dumps(data), 
                        verify=False)

    #ICacheArea
    def get(self, CachableItem):
        """Returns current ICachedItem for ICachableItem or None if not cached"""
        cached_item = self.mapper.get(CachableItem)
        r = requests.get(self.url+"storage/collections/data/"+\
                                        self.collname+'/'+cached_item.getId(),
                            auth=self.auth,
                            headers = {'content-type': 'application/json'},
                            verify=False)
        if r.ok:
            # we need to update the object with the values found in the cache area
            data = r.json()
            for name in self.schema:
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
        for item in CachableSource.items():
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
                        headers = {'content-type': 'application/json'},
                        verify=False)
        if not r.ok:
            raise EnvironmentError("unexpected http response code %s: %s" % (str(r.status_code), r.text))
        self.initialize()
        

    def initialize(self):
        """Instantiates the cache area to be ready for updates"""
        if self.collname in self.current_kv_names():
            return # nothing to do
        # create collection.
        requests.post(self.url+"storage/collections/config",
                            auth=self.auth,
                            headers = {'content-type': 'application/json'},
                            data={'name': self.collname},
                            verify=False)
        # initialize schema
        requests.post(self.url+"storage/collections/config/"+self.collname,
                            auth=self.auth,
                            headers = {'content-type': 'application/json'},
                            data=self.schema,
                            verify=False)
        if self.collname not in self.current_kv_names():
            raise EnvironmentError('expected %s in list of kv collections %s' % (self.collname, str(self.current_kv_names())))

cacheAreaForSplunkKVFactory = Factory(CacheAreaForSplunkKV)
