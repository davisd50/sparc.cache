import os
import unittest
import zope.testrunner
from zope import component
from sparc.testing.fixture import test_suite_mixin
from sparc.testing.testlayer import SPARC_INTEGRATION_LAYER

from sparc.cache import ICachableSource
from sparc.entity import IEntity

class SparcCacheZODBAreaTestCase(unittest.TestCase):
    layer = SPARC_INTEGRATION_LAYER
    sm = component.getSiteManager()

    def setUp(self):
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

    
    
    def test_iterable(self):
        source = component.createObject(u'sparc.cache.source_from_iterable', [self.item1, self.item2])
        self.assertTrue(ICachableSource.providedBy(source))
        self.assertEquals(source.first(), self.item1)
        self.assertEquals([i for i in source.items()], [self.item1, self.item2])


class test_suite(test_suite_mixin):
    package = 'sparc.cache.sources'
    module = 'iterable'
    
    def __new__(cls):
        suite = super(test_suite, cls).__new__(cls)
        suite.addTest(unittest.makeSuite(SparcCacheZODBAreaTestCase))
        return suite


if __name__ == '__main__':
    zope.testrunner.run([
                         '--path', os.path.dirname(__file__),
                         '--tests-pattern', os.path.splitext(
                                                os.path.basename(__file__))[0]
                         ])