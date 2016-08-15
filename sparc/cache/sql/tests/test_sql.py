import os
import zope.testrunner
from sparc.testing.fixture import test_suite_mixin

from sparc.cache.sql.testing import SPARC_CACHE_SQL_INTEGRATION_LAYER

class test_suite(test_suite_mixin):
    layer = SPARC_CACHE_SQL_INTEGRATION_LAYER
    package = 'sparc.cache.sql'
    module = 'sql'


if __name__ == '__main__':
    zope.testrunner.run([
                         '--path', os.path.dirname(__file__),
                         '--tests-pattern', os.path.splitext(
                                                os.path.basename(__file__))[0]
                         ])