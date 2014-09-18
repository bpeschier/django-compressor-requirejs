from itertools import chain
import json
import os
import re
import json

from django.conf import settings
from django.template.loaders.app_directories import app_template_dirs
from django.contrib.staticfiles import finders
from django.apps import apps

from compressor.filters.base import FilterBase


require_pattern = re.compile(r'require\((\[.*\])')
define_pattern = re.compile(r'define\((\[.*\])')


class RequireJSCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        super(RequireJSCompiler, self).__init__(content, filter_type, filename)

    @staticmethod
    def get_template_files():
        template_files = []
        for template_dir in (settings.TEMPLATE_DIRS + app_template_dirs):
            for dir, dirnames, filenames in os.walk(template_dir):
                for filename in filenames:
                    template_files.append(os.path.join(dir, filename))
        return template_files

    @staticmethod
    def get_dependencies_from_match(match):
        # XXX this could use some love
        return json.loads(match.replace("'", '"'))

    def get_module_dependencies(self, path):
        with open(path, 'r') as f:
            content = f.read()
            for match in chain(require_pattern.findall(content), define_pattern.findall(content)):
                for dep in self.get_dependencies_from_match(match):
                    yield dep

    def get_template_dependencies(self):
        for template in self.get_template_files():
            f = open(template, 'r')
            matches = require_pattern.findall(f.read(), re.MULTILINE)
            for match in matches:
                for dep in self.get_dependencies_from_match(match):
                    yield dep

    @staticmethod
    def find_module(name):
        module_js = '{}.js'.format(name)
        module_parts = module_js.split('/')

        path = finders.find(module_js)
        # Allow app alias (static/<app>/js/...)
        if path is None and apps.is_installed(module_parts[0]):
            module_parts.insert(1, 'js')
            path = finders.find('/'.join(module_parts))
        return path

    def resolve_dependencies(self, modules, known):
        for module in [m for m in modules if m not in known]:
            path = self.find_module(module)
            if path:
                known.add(module)
                known.update(self.resolve_dependencies(self.get_module_dependencies(path), known))
        return known

    def input(self, **kwargs):
        if self.filename:
            modules = set(self.get_template_dependencies())
            print(self.resolve_dependencies(modules, set()))

            return 'console.log("{}");'.format(self.filename)
        else:
            raise Exception("Should not get here")
