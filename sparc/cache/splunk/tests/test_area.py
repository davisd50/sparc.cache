import os
import unittest
import zope.testrunner
from zope import component
from sparc.testing.fixture import test_suite_mixin
from sparc.db.splunk.testing import SPARC_DB_SPLUNK_INTEGRATION_LAYER

import requests
from zope.component.eventtesting import getEvents
from zope.interface import alsoProvides, classImplements
from sparc.cache import ICachableItem
from sparc.cache.events import ICacheObjectCreatedEvent
from sparc.cache.events import ICacheObjectModifiedEvent
from sparc.cache.splunk.area import CacheAreaForSplunkKV
from sparc.db.splunk import ISplunkKVCollectionSchema
from sparc.db.splunk.tests.test_kvstore import ITestSchema
from sparc.cache.interfaces import ICachableSource

kv_names = {}
kv_names['test_collection'] = {}
kv_names['test_collection']['field.id'] = "string"
kv_names['test_collection']['field.name'] = "string"
SPARC_DB_SPLUNK_INTEGRATION_LAYER.kv_names.update(kv_names)

class SparcCacheSplunkAreaTestCase(unittest.TestCase):
    level = 2
    layer = SPARC_DB_SPLUNK_INTEGRATION_LAYER
    sm = component.getSiteManager()
    
    def cachable_item(self, id=None, name=None):
        cachable_item = type('TestCachableItem', 
                             (object,), 
                             {
                              'key': 'id',
                              'attributes':{'id':id,'name':name}
                             }
                             )
        def getId(self):
            return self.attributes['id']
        cachable_item.getId = getId
        alsoProvides(cachable_item, ICachableItem)
        return cachable_item()
    
    def kv_id(self, collection):
        kv_id = component.createObject(u'sparc.db.splunk.kv_collection_identifier')
        kv_id.collection = collection
        kv_id.application = self.layer.kv_appname
        kv_id.username = self.layer.kv_username
        return kv_id

    def setUp(self):
        self.tearDown() # destroy any left over kv collections from these tests
        self.mapper = component.createObject(u'sparc.cache.simple_item_mapper', 
                                        key='id',
                                        CacheableItem=self.cachable_item())
        schema = component.createObject(u'sparc.db.splunk.kv_collection_schema')
        schema.update(kv_names['test_collection'])
        self.cache_area = CacheAreaForSplunkKV(self.mapper, 
                                schema, self.layer.sci, 
                                self.kv_id(u"test_collection"))
    
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
        from zope import schema as zschema
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
                                  self.kv_id(u"test_init"))
        self.assertNotIn('test_init', self.layer.get_current_kv_names())
        ca.initialize()
        self.assertIn('test_init', self.layer.get_current_kv_names())
        
        kv_id = self.layer.get_kv_id(u'test_init')
        schema_test = component.getMultiAdapter((self.layer.sci, kv_id,), 
                                                ISplunkKVCollectionSchema)
        self.assertEquals(schema, schema_test)
        
        # add a new field and init again...see if it creates the new field
        ITestSchema.new = zschema.TextLine(title=u'new')
        schema = ISplunkKVCollectionSchema(ITestSchema)
        ca = CacheAreaForSplunkKV(mapper, schema, self.layer.sci, 
                                  self.kv_id(u"test_init"))
        ca.initialize()
        schema_test = component.getMultiAdapter((self.layer.sci, kv_id,), 
                                                ISplunkKVCollectionSchema)
        self.assertEquals(schema, schema_test)
    
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

    def get_cachable_source(self):
        ci1 = self.cachable_item('123','name 1')
        ci2 = self.cachable_item('abc','name 2')
        cs = type('TestCacheSource', (object, ),{'_items': [ci1,ci2]})
        def items(self):
            return self._items
        cs.items = items
        classImplements(cs, ICachableSource)
        return cs()
    
    def test_import_source_and_trim(self):
        count = self.cache_area.import_source(self.get_cachable_source())
        self.assertEquals(count, 2)
        data = self.cache_area._all_ids()
        self.assertEquals(data, set(['abc','123']))
        
        # trim with a ICachablesource
        cs = self.get_cachable_source()
        popped = cs._items.pop()
        counts = self.cache_area.trim(cs)
        self.assertEquals(counts, (0,1,))
        self.assertTrue(self.cache_area.isDirty(popped))
        
        #trim with a iterable of ICahableItem
        trimmed = cs._items[0]
        counts = self.cache_area.trim([popped])
        self.assertEquals(counts, (1,1,))
        self.assertTrue(self.cache_area.isDirty(trimmed))
        self.assertFalse(self.cache_area.isDirty(popped))

# this will insure the doc test clean-up will happen for the created KV collections
kv_names['type1'] = {}
kv_names['type2'] = {}
SPARC_DB_SPLUNK_INTEGRATION_LAYER.kv_names.update(kv_names)
class test_suite(test_suite_mixin):
    package = 'sparc.cache.splunk'
    module = 'area'
    level = 2
    layer = SPARC_DB_SPLUNK_INTEGRATION_LAYER
    
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