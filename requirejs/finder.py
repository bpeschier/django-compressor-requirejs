from itertools import chain
import json
import os
import re

from django.template.loaders.app_directories import app_template_dirs
from django.contrib.staticfiles import finders
from django.conf import settings
import django

require_pattern = re.compile(r'(?:;|\s|>|^)require\s*\(\s*?(\[[^\]]*\])')
define_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?(\[[^\]]*\])')


class ModuleFinder(object):
    """
    Find RequireJS modules in a Django project
    """

    def __init__(self, app_alias=None):
        self.app_alias = app_alias

    #
    # File discovery
    #

    def get_modules(self):
        """
        Main function to query for modules in Django project
        """
        # TODO: work out dependency graph instead of list? Is this really needed for bundles?
        return self.resolve_dependencies(self.get_template_dependencies())

    @staticmethod
    def get_template_files():
        """
        Quick and simple template discovery for TEMPLATE_DIRS and app-based template dirs
        """
        template_files = []
        for template_dir in (settings.TEMPLATE_DIRS + app_template_dirs):
            for directory, dirnames, filenames in os.walk(template_dir):
                for filename in filenames:
                    template_files.append(os.path.join(directory, filename))
        return template_files

    def find_module(self, name):
        """
        Locate a static file for a RequireJS module name.
        """
        module_js = '{}.js'.format(name)

        path = finders.find(module_js)

        # Check for app alias if we cannot find it
        module_parts = module_js.split('/')
        if path is None and self.app_alias and self.is_app_installed(module_parts[0]):
            module_parts.insert(1, self.app_alias)
            path = finders.find('/'.join(module_parts))

        return path

    #
    # Helpers
    #

    @staticmethod
    def get_dependencies_from_match(match):
        """
        Resolve dependencies from the regex match found in a require() or define() call
        """
        # XXX this could use some love, for now we assume a list of strings
        # and convert single quotes into double so we can safely load it as JSON
        return json.loads(match.replace("'", '"'))

    @staticmethod
    def is_app_installed(label):
        """
        Check if app is installed into the Django app cache.
        """
        if django.VERSION >= (1, 7):
            from django.apps import apps

            return apps.is_installed(label)
        else:
            return label in settings.INSTALLED_APPS

    #
    # Dependency discovery
    #

    def get_dependencies(self, content, find_require=True, find_define=True):
        patterns = []
        if find_require:
            patterns.append(require_pattern)
        if find_define:
            patterns.append(define_pattern)

        for match in chain(*[pattern.findall(content) for pattern in patterns]):
            for dep in self.get_dependencies_from_match(match):
                yield dep

    def get_module_dependencies(self, path):
        """
        Load a module and check for require() or define() calls
        """
        with open(path, 'r') as f:
            for dep in self.get_dependencies(f.read()):
                yield dep

    def get_template_dependencies(self):
        """
        Walk through templates defined in the project and find require() calls
        """
        for template in self.get_template_files():
            with open(template, 'r') as f:
                for dep in self.get_dependencies(f.read(), find_define=False):
                    yield dep

    def resolve_dependencies(self, modules, known=None):
        """
        Recursively walk through modules and find their dependencies.
        """
        if known is None:
            known = set()

        for module in [m for m in modules if m not in known]:
            path = self.find_module(module)
            if path:  # only continue if we find the module on disk
                known.add(module)
                # Fetch all module's dependencies
                known.update(self.resolve_dependencies(self.get_module_dependencies(path), known=known))
        return known
