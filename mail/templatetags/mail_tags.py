from django import template
import datetime

register = template.Library()


@register.filter
def hour_or_date(datetime_instance):
    """Intelligent date display:
     * If the date is today, only display the hour
     * if the date is before today, display the day+month"""
    today = datetime.date.today()
    today_midnight = datetime.datetime(today.year, today.month, today.day)
    if datetime_instance > today_midnight:
        time_format = '%H:%M'
    else:
        time_format = '%b %d'

    return datetime_instance.strftime(time_format)
