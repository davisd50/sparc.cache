import sqlalchemy
from sqlalchemy.orm import mapper
from zope.component import getUtility
from zope.component.factory import Factory
from zope.interface import implementer
from zope.schema import getFieldNamesInOrder
from zope.schema.fieldproperty import FieldProperty
from sparc.cache import ICachedItem
from sparc.cache.item import cachedItemMixin
from sparc.db.sql.sa import ISqlAlchemyDeclarativeBase
from sparc.db.sql.sa import sparcBaseMixin
from sparc.db.sql.sa.zs2sa import fieldmap
from sparc.db.sql.sa.zs2sa import transmute

types = {} # mutable module level var to hold created type defs

implementer(ICachedItem)
def SACachedItemFromZopeSchemaInterface(*args, **kwargs):
    """Create a ICachedItem from a Zope schema
    
    Args:
        schema: zope.interface.Interface that has schema attributes
        key: name of schema attribute that is used as unique cached item identifier
    Kwargs:
        base: Optional sqlalchemy declarative base class.  defaults to ISqlAlchemyDeclarativeBase singleton
    """
    schema, key = args[0], args[1]
    
    type_name = schema.getName()[1:]+'CachedItem'
    if type_name not in types:
        base = kwargs['base'] if 'base' in kwargs else getUtility(ISqlAlchemyDeclarativeBase)
        
        table = transmute(schema, base.metadata, add_primary=False, key=key)
        ci_type_params = {'_key':key,
                          '_eq_checked_interfaces':schema}
        ci_type = type(type_name, 
                       (cachedItemMixin, ),
                       ci_type_params)
        mapper(ci_type, table)
        types[type_name] = ci_type
    return types[type_name]()

saCachedItemFromZopeSchemaInterfaceFactory = Factory(SACachedItemFromZopeSchemaInterface)