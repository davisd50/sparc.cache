from sparc.testing.testlayer import SparcZCMLFileLayer
import sparc.testing


class SparcCacheSqlLayer(SparcZCMLFileLayer):
    """Sparc Cache SQL Layer
    
    Some tests will register event subscribers.  this will help to isolate those
    subscriptions for other testing
    """
    
    def setUp(self):
        super(SparcCacheSqlLayer, self).setUp()

    def tearDown(self):

        super(SparcCacheSqlLayer,self).tearDown()

SPARC_CACHE_SQL_INTEGRATION_LAYER = SparcCacheSqlLayer(sparc.testing) #should initialize the ftesting.zcml file
