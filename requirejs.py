from itertools import chain
import os
import re
import json

from django.core.files.base import ContentFile
from django.template.loaders.app_directories import app_template_dirs
from django.contrib.staticfiles import finders
import django

from compressor.conf import settings
from compressor.filters.base import FilterBase
from compressor.js import JsCompressor
from django.utils.safestring import mark_safe


require_pattern = re.compile(r'require\((\[.*\])')
define_pattern = re.compile(r'define\((\[.*\])')
define_replace_pattern = re.compile(r'define\((.*)\)')

REQUIREJS_PATHS = settings.REQUIREJS_PATHS if hasattr(settings, 'REQUIREJS_PATHS') else {}
REQUIREJS_BUNDLES = settings.REQUIREJS_BUNDLES if hasattr(settings, 'REQUIREJS_BUNDLES') else {}


class RequireJSCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        self.charset = charset
        self.attrs = attrs
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
            with open(template, 'r') as f:
                matches = require_pattern.findall(f.read(), re.MULTILINE)
                for match in matches:
                    for dep in self.get_dependencies_from_match(match):
                        yield dep

    def find_module(self, name):
        module_js = '{}.js'.format(name)
        module_parts = module_js.split('/')

        path = finders.find(module_js)
        # Allow app alias (static/<app>/js/...)
        if path is None and self.is_app_installed(module_parts[0]):
            module_parts.insert(1, 'js')
            path = finders.find('/'.join(module_parts))
        return path

    def is_app_installed(self, label):
        if django.VERSION >= (1, 7):
            from django.apps import apps

            return apps.is_installed(label)
        else:
            return label in settings.INSTALLED_APPS

    def resolve_dependencies(self, modules, known=None):
        if known is None:
            known = set()
        for module in [m for m in modules if m not in known]:
            path = self.find_module(module)
            if path:
                known.add(module)
                known.update(self.resolve_dependencies(self.get_module_dependencies(path), known=known))
        return known

    def get_bundle_module(self, module):
        with open(self.find_module(module), 'r') as f:
            content = f.read()
            return define_replace_pattern.sub(r'define("{module}", \1)'.format(module=module), content, re.MULTILINE)

    def get_bundle(self, modules):
        content = [self.get_bundle_module(module) for module in modules]
        return '\n'.join(content)

    def write_bundle(self, name, modules):
        bundle = self.get_bundle(modules)
        return self.write_output(bundle, '{name}.js'.format(name=name))

    @staticmethod
    def write_output(content, basename):
        compressor = JsCompressor()
        filtered = compressor.filter(content, method='input', kind='js')
        output = compressor.filter_output(filtered)
        path = compressor.get_filepath(output, basename=basename)
        # Force write
        compressor.storage.save(path, ContentFile(content.encode(compressor.charset)))
        return mark_safe(compressor.storage.url(path))

    def get_bundle_config(self):
        # TODO: work out dependency graph instead of list
        modules = self.resolve_dependencies(self.get_template_dependencies())

        bundles = {}
        if REQUIREJS_BUNDLES:
            for name, bundle_modules in REQUIREJS_BUNDLES.items():
                bundle_path = self.write_bundle(name, bundle_modules)
                bundles[bundle_path] = list(bundle_modules)
                for m in bundle_modules:
                    modules.discard(m)

        if modules:
            bundles[self.write_bundle('main', modules)] = list(modules)

        return {
            'bundles': bundles,
        }

    @staticmethod
    def get_default_config():
        if django.VERSION >= (1, 7):
            from django.apps import apps

            paths = {
                app.label: '{}/js'.format(app.label) for app in apps.get_app_configs()
            }
        else:
            paths = {
                app.split('.')[-1]: '{}/js'.format(app.split('.')[-1]) for app in settings.INSTALLED_APPS
            }

        paths.update(REQUIREJS_PATHS)

        return {
            'baseUrl': settings.STATIC_URL,
            'paths': paths,
        }

    def input(self, **kwargs):
        if self.filename:
            with open(self.filename, 'r') as f:
                require_content = f.read()
        else:
            require_content = self.content

        config = self.get_default_config()
        if settings.COMPRESS_ENABLED:
            config.update(self.get_bundle_config())

        return "var require = {config};{content}".format(config=json.dumps(config), content=require_content)
