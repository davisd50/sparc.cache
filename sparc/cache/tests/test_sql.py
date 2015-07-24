"""Test
"""
import unittest
from doctest import DocTestSuite
from doctest import DocFileSuite

import sparc.cache

def test_suite():
    return unittest.TestSuite((
        DocFileSuite('sql.txt',
                     package=sparc.cache),))

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')