import uuid

from django.db import models


# Thanks, http://djangosnippets.org/snippets/1262/
class UUIDField(models.CharField):
    """
    Example:
        uuid = UUIDField(primary_key=True, editable=False)
    """

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 64)
        kwargs['blank'] = True
        models.CharField.__init__(self, *args, **kwargs)

    def pre_save(self, model_instance, add):
        if add:
            value = str(uuid.uuid4())
            setattr(model_instance, self.attname, value)
            return value
        else:
            return super(models.CharField, self).pre_save(model_instance, add)


# Thanks, David Cramer
# http://www.davidcramer.net/code/181/custom-fields-in-django.html
class SeparatedValuesField(models.TextField):
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        self.token = kwargs.pop('token', ',')
        super(SeparatedValuesField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if not value: return
        if isinstance(value, list):
            return value
        return value.split(self.token)

    def get_db_prep_value(self, value):
        if not value: return
        assert(isinstance(value, list) or isinstance(value, tuple))
        return self.token.join([unicode(s) for s in value])

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)
