import os
import unittest
import zope.testrunner
from zope import component
from sparc.testing.fixture import test_suite_mixin
from sparc.testing.testlayer import SPARC_INTEGRATION_LAYER

from zope.component.eventtesting import getEvents
from zope.container.btree import BTreeContainer
from zope.container.sample import SampleContainer
from sparc.cache.events import ICacheObjectCreatedEvent
from sparc.cache.events import ICacheObjectModifiedEvent
from sparc.cache import ICacheArea
from sparc.cache import ITrimmableCacheArea
from sparc.entity import IEntity

class SparcCacheZODBAreaTestCase(unittest.TestCase):
    layer = SPARC_INTEGRATION_LAYER
    sm = component.getSiteManager()

    def setUp(self):
        self.sample = SampleContainer()
        self.btree = BTreeContainer()

        self.ca_sample = ICacheArea(self.sample)
        self.ca_btree = ICacheArea(self.btree)
        
        self.entity1 = \
                component.createObject(u'sparc.entity.persistent.entity',
                                       id='1',
                                       name=u'Entity 1')
        self.entity2 = \
                component.createObject(u'sparc.entity.persistent.entity',
                                       id='2',
                                       name=u'Entity 2')
        self.item1 = \
                component.createObject(\
                            u'sparc.cache.simple_cacheable_item_from_schema',
                            'id', IEntity, self.entity1)
        self.item2 = \
                component.createObject(\
                            u'sparc.cache.simple_cacheable_item_from_schema',
                            'id', IEntity, self.entity2)

    
    
    def test_cache(self):
        self.assertIsNone(self.ca_sample.get(self.item1))
        self.assertIsNone(self.ca_btree.get(self.item1))
        self.assertEquals(getEvents(ICacheObjectCreatedEvent), [])
        self.assertEquals(getEvents(ICacheObjectModifiedEvent), [])
        
        cached1_sample = self.ca_sample.cache(self.item1)
        cached1_btree = self.ca_btree.cache(self.item1)
        test_cached1_sample = self.ca_sample.get(self.item1)
        test_cached1_btree = self.ca_sample.get(self.item1)
        self.assertEquals(cached1_sample, test_cached1_sample)
        self.assertEquals(cached1_btree, test_cached1_btree)
        self.assertEquals(len(getEvents(ICacheObjectCreatedEvent)), 2)
        self.assertEquals(getEvents(ICacheObjectModifiedEvent), [])
        
        self.assertIsNone(self.ca_sample.cache(self.item1))
        self.assertIsNone(self.ca_btree.cache(self.item1))
        self.item1.attributes['name'] = 'another name'
        
        test_cached1_sample = self.ca_sample.cache(self.item1)
        test_cached1_btree = self.ca_btree.cache(self.item1)
        self.assertIsNotNone(test_cached1_sample)
        self.assertIsNotNone(test_cached1_btree)
        self.assertNotEquals(cached1_sample, test_cached1_sample)
        self.assertNotEquals(cached1_btree, test_cached1_btree)
        self.assertEquals(cached1_sample.getId(), test_cached1_sample.getId())
        self.assertEquals(cached1_btree.getId(), test_cached1_btree.getId())
        self.assertEquals(len(getEvents(ICacheObjectCreatedEvent)), 2)
        self.assertEquals(len(getEvents(ICacheObjectModifiedEvent)), 2)

        self.assertEquals(len(self.ca_sample.context), 1)
        self.ca_sample.cache(self.item2)
        self.assertEquals(len(self.ca_sample.context), 2)
        self.ca_sample.reset()
        self.assertEquals(len(self.ca_sample.context), 0)
        
        class dummy_source(object):
            def __init__(self, items):
                self._items = items
            def items(self):
                return self._items
        delta = self.ca_sample.import_source(dummy_source([self.item1, self.item2]))
        self.assertEquals(delta, 2)

class SparcTrimCacheZODBAreaTestCase(SparcCacheZODBAreaTestCase):
    
    def setUp(self):
        super(SparcTrimCacheZODBAreaTestCase, self).setUp()

        self.ca_sample = ITrimmableCacheArea(self.sample)
        self.ca_btree = ITrimmableCacheArea(self.btree)

    def test_cache(self):
        self.assertTrue(self.ca_sample.isDirty(self.item1))
        self.assertTrue(self.ca_sample.isDirty(self.item2))
        self.assertTrue(self.ca_btree.isDirty(self.item1))
        self.assertTrue(self.ca_btree.isDirty(self.item2))
        
        self.assertEquals(self.ca_sample.trim([self.item1, self.item2]), (2,0))
        self.assertEquals(self.ca_btree.trim([self.item1, self.item2]), (2,0))
        
        self.assertEquals(self.ca_sample.trim([self.item2]), (0,1))
        self.assertEquals(self.ca_btree.trim([self.item2]), (0,1))
        
        self.assertEquals(self.ca_sample.trim([self.item1, self.item2]), (1,0))
        self.assertEquals(self.ca_btree.trim([self.item1, self.item2]), (1,0))

class test_suite(test_suite_mixin):
    package = 'sparc.cache.zodb'
    module = 'container'
    
    def __new__(cls):
        suite = super(test_suite, cls).__new__(cls)
        suite.addTest(unittest.makeSuite(SparcCacheZODBAreaTestCase))
        suite.addTest(unittest.makeSuite(SparcTrimCacheZODBAreaTestCase))
        return suite


if __name__ == '__main__':
    zope.testrunner.run([
                         '--path', os.path.dirname(__file__),
                         '--tests-pattern', os.path.splitext(
                                                os.path.basename(__file__))[0]
                         ])