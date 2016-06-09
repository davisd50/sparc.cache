import os
import unittest
import zope.testrunner
from zope import component
from sparc.testing.fixture import test_suite_mixin
from sparc.cache.testing import SPARC_CACHE_SPLUNK_INTEGRATION_LAYER

import requests
from zope.component.eventtesting import getEvents
from zope.interface import alsoProvides
from sparc.cache import ICachableItem
from sparc.cache.events import ICacheObjectCreatedEvent
from sparc.cache.events import ICacheObjectModifiedEvent
from sparc.cache.splunk import CacheAreaForSplunkKV
from sparc.db.splunk import ISplunkKVCollectionSchema
from sparc.db.splunk.tests.test_kvstore import ITestSchema

kv_names = {}
kv_names['test_collection'] = {}
kv_names['test_collection']['id'] = "string"
kv_names['test_collection']['name'] = "string"
SPARC_CACHE_SPLUNK_INTEGRATION_LAYER.kv_names.update(kv_names)

class SparcCacheSplunkAreaTestCase(unittest.TestCase):
    level = 2
    layer = SPARC_CACHE_SPLUNK_INTEGRATION_LAYER
    sm = component.getSiteManager()
    
    def cachable_item(self, id=None, name=None):
        cachable_item = type('CachableItem', (object,), {'attributes':{'id':id,'name':name}})
        alsoProvides(cachable_item, ICachableItem)
        return cachable_item
    
    def setUp(self):
        self.tearDown() # destroy any left over kv collections from these tests
        self.mapper = component.createObject(u'sparc.cache.simple_item_mapper', 
                                        key='id',
                                        CacheableItem=self.cachable_item())
        schema = component.createObject(u'sparc.db.splunk.kv_collection_schema')
        schema.update(kv_names['test_collection'])
        self.cache_area = CacheAreaForSplunkKV(self.mapper, 
                                schema, self.layer.sci, 
                                "test_collection", self.layer.kv_appname,
                                self.layer.kv_username)
    
    def tearDown(self):
        collections = ['test_init']
        for name in [n for n in  collections\
                                if n in self.layer.get_current_kv_names()]:
            requests.delete(self.layer.url+"storage/collections/config/"+name,
                                auth=self.layer.auth,
                                verify=False)
        names = self.layer.get_current_kv_names()
        for name in collections:
            if name in names:
                raise EnvironmentError('unexpectedly found %s in kv collections %s' % (name, str(self.kv_names.keys())))

    def test_initialize(self):
        cachable_item = type('CachableItem', (object,),
                             {'attributes':{},'key':'int'})
        cachable_item.attributes = {n:None for n in ITestSchema}
        alsoProvides(cachable_item, ICachableItem)
        mapper = component.createObject(u'sparc.cache.simple_item_mapper', 
                                        key='int',
                                        CacheableItem=cachable_item)#,
                                        #filter=lambda x,y: str(y))
        schema = ISplunkKVCollectionSchema(ITestSchema)
        ca = CacheAreaForSplunkKV(mapper, schema, self.layer.sci, 
                                  "test_init", self.layer.kv_appname,
                                  self.layer.kv_username)
        self.assertNotIn('test_init', ca.current_kv_names())
        ca.initialize()
        self.assertIn('test_init', ca.current_kv_names())
    
    def test_get_cache(self):
        cachable_item = self.cachable_item('123','a name')
        self.assertIsNone(self.cache_area.get(cachable_item))
        self.assertEquals(getEvents(ICacheObjectCreatedEvent), [])
        self.assertEquals(getEvents(ICacheObjectModifiedEvent), [])
        
        cached_item = self.cache_area.cache(cachable_item)
        test_cached_item = self.cache_area.get(cachable_item)
        self.assertEquals(cached_item, test_cached_item)
        self.assertEquals(len(getEvents(ICacheObjectCreatedEvent)), 1)
        self.assertEquals(getEvents(ICacheObjectModifiedEvent), [])
        
        self.assertIsNone(self.cache_area.cache(cachable_item))
        cachable_item.attributes['name'] = 'another name'

        test_cached_item = self.cache_area.cache(cachable_item)
        self.assertIsNotNone(test_cached_item)
        self.assertNotEquals(cached_item, test_cached_item)
        self.assertEquals(cached_item.getId(), test_cached_item.getId())
        self.assertEquals(len(getEvents(ICacheObjectCreatedEvent)), 1)
        self.assertEquals(len(getEvents(ICacheObjectModifiedEvent)), 1)
    
    def test_isDirty(self):
        cachable_item = self.cachable_item('abcd','a name')
        self.assertTrue(self.cache_area.isDirty(cachable_item))
        self.cache_area.cache(cachable_item)
        self.assertFalse(self.cache_area.isDirty(cachable_item))
        cachable_item = self.cachable_item('abcd','another name')
        self.assertTrue(self.cache_area.isDirty(cachable_item))
        self.cache_area.cache(cachable_item)
        self.assertFalse(self.cache_area.isDirty(cachable_item))
    
    def test_reset(self):
        cachable_item = self.cachable_item('abcd','a name')
        self.cache_area.cache(cachable_item)
        self.cache_area.reset()
        self.assertTrue(self.cache_area.isDirty(cachable_item))
        self.cache_area.cache(cachable_item)
        self.assertFalse(self.cache_area.isDirty(cachable_item))
    
    def test_import_source(self):
        ci1 = self.cachable_item('123','name 1')
        ci2 = self.cachable_item('abc','name 2')
        cs = type('TestCacheSource', (object, ),{'items': None})
        def items(self):
            for ci in [ci1, ci2]:
                yield ci
        cs.items = items.__get__(self, cs.__class__) # creates a bound method for TestCacheSource type
        count = self.cache_area.import_source(cs)
        self.assertEquals(count, 2)
    
class test_suite(test_suite_mixin):
    package = 'sparc.cache'
    module = 'splunk'
    
    def __new__(cls):
        suite = super(test_suite, cls).__new__(cls)
        suite.addTest(unittest.makeSuite(SparcCacheSplunkAreaTestCase))
        return suite


if __name__ == '__main__':
    zope.testrunner.run([
                         '--path', os.path.dirname(__file__),
                         '--tests-pattern', os.path.splitext(
                                                os.path.basename(__file__))[0]
                         ])