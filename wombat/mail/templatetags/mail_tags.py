import datetime

from django import template
from django.utils.tzinfo import LocalTimezone

register = template.Library()

@register.filter
def numberize(instance, count_attr):
    """
        Filter used to display directory (n) where n is the
        number of unread messages:
    """
    value = getattr(instance, count_attr)
    if value:
        return "%s (%d)" % (instance, value)
    return instance


@register.filter
def hour_or_date(datetime_instance):
    """Intelligent date display:
     * If the date is today, only display the hour
     * if the date is before today, display the day+month
    """
    today = datetime.date.today()
    today_midnight = datetime.datetime(today.year, today.month, today.day)
#            tzinfo=LocalTimezone(datetime.datetime.now()))
    if datetime_instance > today_midnight:
        time_format = '%H:%M'
    elif datetime_instance.year < today.year:
        time_format = '%d/%m/%y'
    else:
        time_format = '%b %d'

    return datetime_instance.strftime(time_format)


@register.filter('from')
def _from(value):
    if len(value) == 1:
        tokens = value[0].split(' ')
        if len(tokens) == 1:
            return tokens[0]
        return ' '.join(tokens[:-1])
    if len(value) > 2:
        return ', '.join(name.split()[0] for name in value[:2]) + " ..."
    return ', '.join(name.split()[0] for name in value)
