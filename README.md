sparc.cache
===========

Data caching components for the SPARC platform.

SQL Cache Area
----------------
SQL implementation of ICacheArea, providing a mechanism to store items 
implementing either ICachableItem (a single item) or ICachableSource
(many items).

This implementation utilizes SQLAlchemy to provide abstraction from the 
specific SQL technology (MySQL, Oracle, SQL Server, etc) to be used.  Also,
this is implemented as a ZCA multi-adapter...allowing easy lookup given
an instance of ISqlAlchemySession and ICachedItemMapper.

Although we provide a *very* flexible implementation for caching information,
this flexibility comes at the cost of some added complexities.  We use ZCA as a 
framework to help us manage the complexity.

Even though, technically, this class can be used outside of ZCA...our examples
will use ZCA because it helps to simplify the explanation.


Cachable Item
----------------
Of course, as a first step, we need some information that is to be cached.
We need structured information that our SQL Cache Area object can understand.
We have the ICachableItem interface to help us here.  So as a first step,
we'll create an implementation of this interface.

    >>> from zope.interface import implements
    >>> from sparc.cache import ICachableItem
    >>> class myItem(object):
    ...     implements(ICachableItem)
    ...     def __init__(self, attributes = None):
    ...         self.key = 'ENTRY #'
    ...         self.attributes = attributes
    ...     def getId(self):
    ...         return self.attributes[self.key]
    ...     def validate(self):
    ...         if not self.attributes.has_key(self.key):
    ...             raise KeyError("expected item's attributes to have entry for key field: %s", self.key)
    ...         if not self.attributes[self.key]:
    ...             raise ValueError("expected item's key attribute to have a non-empty value")

Notice...we did not need to explicitly add members in the class that represent
individually cachable information (i.e. column definitions).  Instead we
have single myItem.attributes which will contain a Dictionary of the
information that is to be cached in key, value pairs.

Also notice...we had to specify the key name of the attribute entry which will
be used to uniquely identify the item within a group of items.

Although the above code shows how to create the implementation, mostly it is 
boiler plate so we have a readily available mixin class to help simplify 
things for us.

    >>> del(myItem)
    >>> from sparc.cache.item import cachableItemMixin
    >>> class myItem(cachableItemMixin):
    ...     def __init__(self, attributes=None):
    ...         super(myItem, self).__init__('ENTRY #', attributes)


Finally, we create a factory...whose responsibility is simply to generate new 
instances of our implementation.

    >>> from zope.component.factory import IFactory, Factory
    >>> myCachableItemFactory = Factory(myItem, 'myCachableItemFactory')

Cached Item
----------------
Information that has been cached may require some subtle translations from the
original information source (ICachableItem).  For example, if the cachable 
item has a date string then it would be nice to store that information in
the DB as a datetime type...therefore allowing date searches.  IF we just
stored the information as a string-type...we couldn't utilze the DB's full
capabilities for type-specific searching.

For this, and other reasons, we need a new data structure (class) that will
represent the information after it has been cached.  For this task, we
have the ICachedItem interface.  Again, we require an implementation of this
interface to do anything useful.

    >>> import sqlalchemy.ext.declarative
    >>> class myBaseMixin(object):
    ...     @sqlalchemy.ext.declarative.declared_attr
    ...     def __tablename__(cls):
    ...         return cls.__name__.lower()
    ...         __mapper_args__= {'always_refresh': True}
    ...     def __repr__(self):
    ...        return "<" + self.__class__.__name__ + "(id: '%s'')>" % (self.getId())

We'll also want to get ahold of a SQL Alchemy ORM Delcatative Base object. 
We can do this via a singleton utility providing ISqlAlchemyDeclarativeBase.

    >>> from zope.component import getUtility
    >>> from sparc.db.sql.sa import ISqlAlchemyDeclarativeBase
    >>> Base = getUtility(ISqlAlchemyDeclarativeBase)
        
    >>> from sparc.cache import ICachedItem
    >>> import sqlalchemy
    >>> from datetime import date, timedelta
    >>> class myCachedItem(myBaseMixin, Base):
    ...     implements(ICachedItem)
    ...     entry_number = sqlalchemy.Column(sqlalchemy.BigInteger(), primary_key=True)
    ...     logged_date = sqlalchemy.Column(sqlalchemy.DateTime(),nullable=True)
    ...     def getId(self):
    ...         return self.entry_number
    ...     def __eq__(self, instance):
    ...         if not isinstance(instance, self.__class__):
    ...             return False
    ...         if self.entry_number != instance.entry_number:
    ...             return False
    ...         if self.logged_date - instance.logged_date != timedelta(0):
    ...             return False
    ...         return True
    ...     def __ne__(self, instance):
    ...         return not self.__eq__(instance)

This implementation is a bit more tricky than our myItem object from above.
First thing to note is our dependency on sqlalchmeny.  This is an 
implementation-specific dependency...driven by our base requirement to allow
information to be stored in a DB via the sqlalchemy abstraction layer.  Other
than conformance to the ICachedItem interface requirements, this acts like a
normal SQL Alchemy persistent object class

But once again, the above implementation is not that fun to write out, so we 
have a ready-to-use mixin class to help things out.

    >>> del(myCachedItem)
    >>> from sparc.cache.item import cachedItemMixin
    >>> from zope.interface import alsoProvides
    >>> Base = sqlalchemy.ext.declarative.declarative_base() # we need to reset this, cause myCachedItem is already defined above
    >>> alsoProvides(Base, ISqlAlchemyDeclarativeBase) # we'll mark it so it can be used in ZCA
    >>> class myCachedItem(cachedItemMixin, myBaseMixin, Base):
    ...     _key = 'entry_number'
    ...     entry_number = sqlalchemy.Column(sqlalchemy.BigInteger(), primary_key=True)
    ...     logged_date = sqlalchemy.Column(sqlalchemy.DateTime(),nullable=True)

Finally (like above), we created factory...whose responsibility is simply to 
generate new instances of our implementation.

    >>> from zope.component.factory import IFactory, Factory
    >>> myCachedItemFactory = Factory(myCachedItem, 'myCachedItemFactory')

Cached Item Mapper
-------------------
Now that we have two different classes, one representing information we want to
cache and the other representing the information after it has been cached, we need 
a way to relate the 2 different classes.  For this task, we have the
ICachedItemMapper interface.  This class provides a mechanism to populate
an ICachedItem from information stored in a ICachableItem.

    >>> from zope.component import adapts
    >>> from sparc.cache.interfaces import ICachedItemMapper, ICachableSource
    >>> from sparc.cache.sources import normalizedDateTime, normalizedDateTimeResolver
    >>> class myItemCacheMapper(object):
    ...     implements(ICachedItemMapper)
    ...     adapts(ICachableSource)
    ...     mapper = {
    ...            'entry_number'   :'ENTRY #', 
    ...            'logged_date'    :normalizedDateTime('LOGGED DATE')
    ...           }
    ...     def __init__(self, CachableSource):
    ...         self.cachableSource = CachableSource
    ...     def key(self):
    ...         for _key, _value in self.mapper.iteritems():
    ...             if _value == self.cachableSource.key():
    ...                 return _key
    ...         raise LookupError("expected to find matching cache key for given source key via map lookup")
    ...     def factory(self):
    ...         return myCachedItem()
    ...     def get(self, sourceItem):
    ...         _cachedItem = self.factory()
    ...         _cachedItem.entry_number = int(sourceItem.attributes['ENTRY #'])
    ...         _cachedItem.logged_date = normalizedDateTimeResolver(self.logged_date).manage(sourceItem.attributes['LOGGED DATE'])
    ...         return _cachedItem

For the purpose of illustration, the above class fully implements the 
ICachedItemMapper interface.  However, since it's not fun to create this
type of class, there's an available mixin class to make things a bit simpler
to read/write

    >>> del(myItemCacheMapper)
    >>> from sparc.cache.sql import SqlObjectMapperMixin
    >>> class myItemCacheMapper(SqlObjectMapperMixin):
    ...     mapper = {
    ...            'entry_number'   :'ENTRY #', 
    ...            'logged_date'    :normalizedDateTime('LOGGED DATE')
    ...           }

Much nicer to look at.  Also note the normalizedDateTime() reference.  This
class is an implementation of the IManagedCachedItemMapperAttributeKeyWrapper
interface.  The interface is simple...it needs to supply a __call__() method
that returns the string key name.

Registration
----------------
We've now created classes that represent information in its pre and post
cached state, and also a mapper for the two states.  Things are about to get
interesting.  Before we move forward, we'll add the myItemCacheMapper()
component into the ZCA registry to allow interface-based lookups.

    >>> from zope.component import getGlobalSiteManager
    >>> gsm = getGlobalSiteManager()
    >>> gsm.registerAdapter(myItemCacheMapper, (ICachableSource, IFactory), ICachedItemMapper)

Data Source
----------------
Up until now, we've really only dealt with data definitions.  You might be 
asking..."so where's the data?".  We have the ICachableSource interface to 
deal with data sources.  But first, we need to start with the actual data.
We'll use the test_csvdata.csv file located under the 
sparc.cache.sources.tests directory.

    >>> import os
    >>> csv_file = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'sources' + os.sep + 'tests' + os.sep + 'test_csvdata.csv'

We can now create instances of sparc.cache.sources.csvdata.CSVSource via 
its factory.  This object will be used to generate ICachableItem objects for
each valid CSV row entry.

    >>> from zope.component import createObject
    >>> myCSVSource = createObject('cache.sources.CSVSourceFactory', csv_file, myCachableItemFactory)

Let's run a few quick test to make sure the data source is sane

    >>> item = myCSVSource.first()
    >>> item.attributes['ENTRY #']
    '9098328463'
    >>> item.attributes['LOGGED DATE']
    '6/18/2014 16:28'
    >>> item.getId()
    '9098328463'
    >>> item.validate()

Database Connection
----------------
To work with a database, we need to connect to it per SQLAlchemy instructions.
We'll use a simple SQLite memory database for this example.
        
    >>> from sqlalchemy import create_engine
    >>> engine = create_engine('sqlite:///:memory:')
    >>> from sqlalchemy.orm import sessionmaker
    >>> Session = sessionmaker(bind=engine)
    >>> session = Session()

We need to provide  the ISqlAlchemySession marker interface to the session 
object to enable easy ZCA based component lookup for adapters.

    >>> from zope.interface import directlyProvides
    >>> from sparc.db.sql.sa import ISqlAlchemySession
    >>> directlyProvides(session, ISqlAlchemySession)

Load the Cache!!!
----------------
OK, it was a bit complicated to get here...but now we'll see the fruits of 
our labor.  Our actual caching interface is defined by ITransactionalCacheArea.  
We've implemented this interface via an adapter located at
sparc.cache.sql.SqlObjectCacheArea.  This adapter is already registered, so
we can look it up.

    >>> from sparc.cache import ITransactionalCacheArea
    >>> from zope.component import getMultiAdapter
    >>> myMapper = getMultiAdapter((myCSVSource, myCachedItemFactory), ICachedItemMapper) # get our mapper via our adapter implementation
    >>> mySqlObjectCacheArea = getMultiAdapter((Base, session, myMapper), ITransactionalCacheArea)

One more final activity...we need to initialize (i.e. create the DB tables) 
the storage area.

    >>> mySqlObjectCacheArea.initialize()

whew...that was a lot of work...now we can finally use it.  let's start
by getting one of our cachable items in hand.

    >>> item = myCSVSource.first()
    >>> item.getId()
    '9098328463'

Let's make sure our mapper works ok.

    >>> myMapper.get(item).getId()
    9098328463
        
This item hasn't been cached yet

    >>> mySqlObjectCacheArea.get(item)
    >>> mySqlObjectCacheArea.isDirty(item)
    True
    >>> cached = mySqlObjectCacheArea.cache(item)
    >>> cached.getId()
    9098328463
    >>> mySqlObjectCacheArea.isDirty(item)
    False
    >>> item.attributes['LOGGED DATE'] = '6/18/2014 16:28' # same as orig
    >>> mySqlObjectCacheArea.isDirty(item)
    False
    >>> mySqlObjectCacheArea.cache(item)
    False
    >>> item.attributes['LOGGED DATE'] = '6/25/2014 16:28' # new date
    >>> mySqlObjectCacheArea.isDirty(item)
    True
    >>> myMapper.get(item).getId()
    9098328463
        
Let's test the transactional features

    >>> mySqlObjectCacheArea.rollback()
    >>> mySqlObjectCacheArea.isDirty(item)
    True
    >>> cached = mySqlObjectCacheArea.cache(item)
    >>> cached.getId()
    9098328463
    >>> mySqlObjectCacheArea.isDirty(item)
    False
    >>> mySqlObjectCacheArea.commit()
    >>> mySqlObjectCacheArea.isDirty(item)
    False
    >>> item = myCSVSource.first() # this resets the date from above
    >>> mySqlObjectCacheArea.isDirty(item)
    True
    >>> cached = mySqlObjectCacheArea.cache(item)
    >>> cached.getId()
    9098328463
    >>> mySqlObjectCacheArea.commit()

 Let's get the item directly from the DB and make sure it acts like a
 ICachedItem
 
    >>> mySqlObjectCacheArea.session.expunge(cached)
    >>> cached = mySqlObjectCacheArea.get(item)
    >>> cached.getId()
    9098328463
        
Now lets do a bulk import...when we import it will bring in 1 less
than the total CSV source (because the first entry already done and does not
require an update)

    >>> mySqlObjectCacheArea.import_source(myCSVSource)
    3