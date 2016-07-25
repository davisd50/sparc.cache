import os
import unittest
import zope.testrunner
from zope import component
from sparc.testing.fixture import test_suite_mixin
from sparc.testing.testlayer import SPARC_INTEGRATION_LAYER

from zope import schema
from zope.interface import Interface
class ITestSchema(Interface):
    id = schema.Int(title=u"int")
    date = schema.Date(title=u"date", required=False)
    datetime = schema.Datetime(title=u"datetime", required=False)
    decimal = schema.Decimal(title=u"decimal", required=False)
    float = schema.Float(title=u"float", required=False)
    bool = schema.Bool(title=u"bool", required=False)
    ip = schema.DottedName(title=u"ip",min_dots=3,max_dots=3, required=False)
    ascii = schema.ASCII(title=u"ascii", required=False)
            
class SparcCacheSplunkAreaTestCase(unittest.TestCase):
    layer = SPARC_INTEGRATION_LAYER
    sm = component.getSiteManager()
    
    def test_sql_cached_item_from_schema(self):
        from z3c.saconfig.interfaces import IEngineFactory
        from sparc.db.sql.sa import ISqlAlchemyDeclarativeBase
        import transaction
        Base = component.getUtility(ISqlAlchemyDeclarativeBase)
        
        ci1 = component.createObject(u'sparc.cache.sa_cached_item_from_schema',
                                    ITestSchema, 'id')
        ci2 = component.createObject(u'sparc.cache.sa_cached_item_from_schema',
                                    ITestSchema, 'id')
        myEngine = component.getUtility(IEngineFactory, name="memory_engine")()
        Base.metadata.create_all(myEngine)
        
        from z3c.saconfig import named_scoped_session
        Session = named_scoped_session('memory_session')
        session = Session()
        
        ci1.id = 123
        ci1.float = 1.23
        ci1.bool = True
        
        ci2.id = 234
        ci2.float = 2.34
        ci2.bool = True
        
        session.add_all([ci1, ci2])
        transaction.commit()
        
        self.assertEquals(len(session.query(ci1.__class__).all()), 2)
        

class test_suite(test_suite_mixin):
    package = 'sparc.cache.sql'
    module = 'item'
    
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