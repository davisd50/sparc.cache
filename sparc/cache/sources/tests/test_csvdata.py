"""Test
"""
import unittest
from doctest import DocFileSuite

import sparc.cache.sources

def test_suite():
    return unittest.TestSuite((
        DocFileSuite('csvdata.txt',
                     package=sparc.cache.sources),))

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')