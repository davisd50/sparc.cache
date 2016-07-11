from zope.component import adapts
from zope.interface import implements
from zope.schema import getFieldNames
from sparc.entity import IEntity
from interfaces import ICachableItem
from item import cachableItemMixin

class CachableItemForEntity(cachableItemMixin):
    implements(ICachableItem)
    adapts(IEntity)
    
    def __init__(self, context):
        self.context = context
        attributes = {}
        for name in getFieldNames(IEntity):
            attributes[name] = getattr(context, name)
        super(CachableItemForEntity, self).__init__(key='id', 
                                                  attributes=attributes)