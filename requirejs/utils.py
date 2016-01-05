from django.conf import settings
import django


def get_app_template_dirs():
    if django.VERSION < (1, 8):
        # noinspection PyUnresolvedReferences
        from django.template.loaders.app_directories import app_template_dirs
    else:  # Django 1.8's template loader is refactored
        # noinspection PyUnresolvedReferences
        from django.template.utils import get_app_template_dirs

        app_template_dirs = get_app_template_dirs('templates')
    return list(app_template_dirs)


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
