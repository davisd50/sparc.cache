from setuptools import setup, find_packages
import os

version = '0.0.3'

setup(name='sparc.cache',
      version=version,
      description="Data caching components for the SPARC platform",
      long_description=open("README.md").read() + "\n" +
                       open("HISTORY.txt").read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
      ],
      keywords=['zca'],
      author='David Davis',
      author_email='davisd50@gmail.com',
      url='https://github.com/davisd50/sparc.cache',
      download_url = '',
      license='MIT',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['sparc'],
      include_package_data=True,
      package_data = {
          '': ['*.zcml']
        },
      zip_safe=False,
      install_requires=[
          'setuptools',
          'SQLAlchemy',
          'requests', # splunk REST calls
          'zope.event',
          'zope.lifecycleevent',
          'sparc.common',
          'sparc.db'
          # -*- Extra requirements: -*-
      ],
      tests_require=[
          'sparc.testing'
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
