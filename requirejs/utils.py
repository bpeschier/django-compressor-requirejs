from django.conf import settings
import django


def is_app_installed(label):
    """
    Check if app is installed into the Django app cache.
    """
    if django.VERSION >= (1, 7):
        from django.apps import apps

        return apps.is_installed(label)
    else:
        return label in settings.INSTALLED_APPS


def get_installed_app_labels():
    if django.VERSION >= (1, 7):
        from django.apps import apps

        return [app.label for app in apps.get_app_configs()]
    else:
        return [app.split('.')[-1] for app in settings.INSTALLED_APPS]
