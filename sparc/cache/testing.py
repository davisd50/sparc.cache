import requests
import warnings
import xml.etree.ElementTree as ET
from zope import component
from sparc.testing.testlayer import SparcZCMLFileLayer
import sparc.testing

class SparcCacheSplunkLayer(SparcZCMLFileLayer):
    
    """Tuple of KV collection definitions.
    
    This should be initialized by tests.  This is a 2-dimensional dictionary.  
    The outer dictionary key should be the kv collection name.  The value of 
    this dict should be another dict describing the collection schema.
    """
    kv_names = {}
    
    kv_username = 'nobody' # 'nobody' is typical to let all users see the KV collection
    kv_appname = 'search'
     
    
    @property
    def sci(cls):
        sci = component.createObject(
                            u"sparc.db.splunk.splunk_connection_info_factory")
        sci['host'] = 'splunk_testing_host' # NOT PROD HOST!!!!!...easiest to set this in your host file
        sci['port'] = '8089'
        sci['username'] = 'admin'
        sci['password'] = 'admin'
        return sci
    
    @property
    def url(self):
        sci = self.sci
        return 'https://'+sci['host']+':'+sci['port']+'/servicesNS/' \
                                    +self.kv_username+'/'+self.kv_appname+'/'
    
    @property
    def auth(self):
        return (self.sci['username'], self.sci['password'], )
    
    def get_current_kv_names(self):
        """Return String names of current available Splunk KV collections"""
        re = requests.get(self.url+"storage/collections/config",auth=self.auth, verify=False)
        root = ET.fromstring(re.text)
        for entry in root.findall('./{http://www.w3.org/2005/Atom}entry'):
            name = entry.find('{http://www.w3.org/2005/Atom}title').text
            if not name:
                raise ValueError('unexpectedly found empty collection title')
            yield name
        
    
    def _destroy_kv_collections(self):
        for name in [n for n in self.kv_names if n in self.get_current_kv_names()]:
            requests.delete(self.url+"storage/collections/config/"+name,
                                auth=self.auth,
                                verify=False)
        names = self.get_current_kv_names()
        for name in self.kv_names:
            if name in names:
                raise EnvironmentError('unexpectedly found %s in kv collections %s' % (name, str(self.kv_names.keys())))
    
    def _create_kv_collections(self):
        for name in self.kv_names:
            requests.post(self.url+"storage/collections/config",
                                auth=self.auth,
                                headers = {'content-type': 'application/json'},
                                data={'name': name},
                                verify=False)
            requests.post(self.url+"storage/collections/config/"+name,
                                auth=self.auth,
                                headers = {'content-type': 'application/json'},
                                data=self.kv_names[name],
                                verify=False)
            if name not in self.get_current_kv_names():
                raise EnvironmentError('expected %s in list of kv collections %s' % (name, str(self.get_current_kv_names())))
    
    def setUp(self):
        super(SparcCacheSplunkLayer, self).setUp()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore") # ignore https cert warnings
            self._destroy_kv_collections()
            self._create_kv_collections()

    def tearDown(self):
        with warnings.catch_warnings():
            self._destroy_kv_collections()
            warnings.simplefilter("ignore") # ignore https cert warnings
        super(SparcCacheSplunkLayer,self).tearDown()

warnings.warn("This test layer requires a running Splunk instance.  See %s for connection information." % __file__)
SPARC_CACHE_SPLUNK_INTEGRATION_LAYER = SparcCacheSplunkLayer(sparc.testing) #should initialize the ftesting.zcml file
