from zope.interface import implements
from zope.component.factory import Factory
import os.path
from csv import DictReader

from sparc.cache.interfaces import ICachableSource

import sparc.common.log
import logging
logger = logging.getLogger('sparc.cache.sources.csvdata')

class CSVSource(object):
    
    implements(ICachableSource)
    
    def __init__(self, source, factory, key = None):
        """Initialize the CSV data source
        
        The CSV data source, where the first data row in the represented file
        contains the field headers (names).
        
        Args:
            source: This can be a String, a csv.DictReader, or a generic object
                 that supports the iterator protocol (see csv.reader).  If 
                 this is a String, it should point to either a CSV file, 
                 or a directory containing CSV files.  If it is a 
                 object supporting the iterator protocol, each call to next()
                 should return a valid csv line.
            factory: A callable that implements zope.component.factory.IFactory 
                 that generates instances of ICachableItem.
            key: String name of CSV header field that acts as the unique key for each 
                 CSV item entry (i.e. the primary key field)
        
        Raises:
            ValueError: if string source parameter does not point a referencable file or directory
        
        """
        # TODO: This class current has more methods than ICachableSource.  We either 
        #       need to update the interface, or create a new one for the extra methods
        self._key = key
        self.source = source
        self.factory = factory
        self._files = list()
        self._csv_dictreader_list = list()
        
        if isinstance(source, str):
            if os.path.isfile(source):
                _file = open(source,'rb')
                self._files.append(_file)
                self._csv_dictreader_list.append(DictReader(_file))
            elif os.path.isdir(source):
                for _entry in os.listdir(source):
                    _file = open(_entry,'rb')
                    self._files.append(_file)
                    self._csv_dictreader_list.append(DictReader(_file))
            else:
                raise ValueError("expected string source parameter to reference a valid file or directory: " + str(source))
        elif isinstance(source, DictReader):
            self._csv_dictreader_list.append(source)
        else:
            self._csv_dictreader_list.append(DictReader(source))
        

    def __del__(self):
        """Object cleanup
    
        This will close all open file handles held by the object.
        """
        for f in self._files:
            f.close()
    
    def key(self):
        """Returns string identifier key that marks unique item entries (e.g. primary key field name)"""
        return self._key if self._key else self.factory().key
    
    def items(self):
        """Returns a generator of available ICachableItem in the ICachableSource
        """
        for dictreader in self._csv_dictreader_list:
            for entry in dictreader:
                item = self.factory()
                item.key = self.key()
                item.attributes = entry
                try:
                    item.validate()
                except Exception as e:
                    logger.debug("skipping entry due to item validation exception: %s", str(e))
                    continue
                logger.debug("found validated item in CSV source, key: %s", str(item.attributes[self.key()]))
                yield item
    
    def getById(self, Id):
        """Returns ICachableItem that matches id
        
        Args:
            id: String that identifies the item to return whose key matches
        """
        # we need to create a new object to insure we don't corrupt the generator count
        csvsource = CSVSource(self.source, self.factory, self.key())
        try:
            for item in csvsource.items():
                if Id == item.getId():
                    return item
        except StopIteration:
            return None
    
    def first(self):
        """Returns the first ICachableItem in the ICachableSource"""
        # we need to create a new object to insure we don't corrupt the generator count
        csvsource = CSVSource(self.source, self.factory, self.key())
        try:
            item = csvsource.items().next()
            return item
        except StopIteration:
            return None
        

CSVSourceFactory = Factory(CSVSource, 'CSVSourceFactory', 'generates CSVSource objects')