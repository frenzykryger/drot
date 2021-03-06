import contextlib
import inspect


def model(*whitelist, **kwargs):
    """Decorate class, making it suitable for dict <-> object conversion.
    """
    if len(whitelist) == 1 and isinstance(whitelist[0], type):
        raise AssertionError("This decorator should NOT be used like that: "
                             "@model. "
                             "Write @model() or @simple_model instead")

    def _class_wrapper(clazz):
        if not getattr(clazz, '_drotted', False):
            # Respect base class if it was drotted too
            clazz._drot_parser_hooks = {}
            clazz._drot_mapping_attributes = set([])
            clazz._drot_property_map = {}

        clazz._drotted = True
        clazz._drot_parser_hooks.update(kwargs)

        clazz.to_dict = _to_dict
        clazz.to_object = _to_object
        if whitelist:
            attributes = set(whitelist)
        else:
            attributes = set(k for k, v in vars(clazz).iteritems()
                             if _is_attribute(v)
                             and not k.startswith('_'))
        clazz._drot_mapping_attributes.update(attributes)

        property_map = dict((v.fget.__name__, v.fset)
                            for k, v in vars(clazz).iteritems()
                            if _is_property_setter(v))
        clazz._drot_property_map.update(property_map)
        return clazz
    return _class_wrapper


simple_model = model()


def _is_function(arg):
    return callable(arg) or inspect.ismethoddescriptor(arg)


def _is_property_getter(arg):
    return isinstance(arg, property) and arg.fset


def _is_property_setter(arg):
    return isinstance(arg, property) and arg.fset is None


def _is_attribute(arg):
    return not (_is_function(arg) or _is_property_setter(arg))


def _to_dict(self, excluded=None):
    """Transforms object to it's dictionary representation"""
    idset = set([])
    with _memorized(self, idset):
        return _to_dict_internal(self, idset, excluded=excluded)


def _to_dict_internal(self, idset, excluded=None):
    result = {}
    for key in self._drot_mapping_attributes - set(excluded or []):
        if hasattr(self, key):
            item = getattr(self, key)
            result[key] = _transform_item(item, idset)
    return result


@classmethod
def _to_object(cls, dictionary):
    """Creates object from it's dictionary representation
    with respect to specified parsers"""
    dictionary = dict((k, v) for k, v in dictionary.iteritems()
                      if k in cls._drot_mapping_attributes)

    item = cls()
    for key, value in dictionary.iteritems():

        if key in cls._drot_parser_hooks:
            value = cls._drot_parser_hooks[key](value)

        if key in cls._drot_property_map:
            cls._drot_property_map[key](item, value)
        else:
            setattr(item, key, value)
    return item


def _check_reference_cycle(item, idset):
    if idset and id(item) in idset:
        raise ValueError("Reference cycle: "
                         "item %s shouldn't reference itself" % repr(item))


@contextlib.contextmanager
def _memorized(item, idset):
    idset.add(id(item))
    yield
    idset.remove(id(item))


def _transform_item(item, idset):
    """Transform item to it's dictionary representation"""

    _check_reference_cycle(item, idset)
    with _memorized(item, idset):
        if getattr(item, '_drotted', False):
            return _to_dict_internal(item, idset=idset)

        if isinstance(item, list):
            return [_transform_item(member, idset) for member in item]

        if isinstance(item, dict):
            return dict((key, _transform_item(item[key], idset))
                        for key in item)
    return item
