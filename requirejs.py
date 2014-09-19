from itertools import chain
import os
import re
import json
from compressor.js import JsCompressor

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loaders.app_directories import app_template_dirs
from django.contrib.staticfiles import finders
from django.apps import apps

from compressor.filters.base import FilterBase
from django.utils.safestring import mark_safe


require_pattern = re.compile(r'require\((\[.*\])')
define_pattern = re.compile(r'define\((\[.*\])')
define_replace_pattern = re.compile(r'define\((.*)\)')


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
            with open(template, 'r') as f:
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

    def write_output(self, content, basename):
        compressor = JsCompressor()
        filtered = compressor.filter(content, method='input', kind='js')
        output = compressor.filter_output(filtered)
        path = compressor.get_filepath(output, basename=basename)
        # Force write
        compressor.storage.save(path, ContentFile(content.encode(compressor.charset)))
        return mark_safe(compressor.storage.url(path))

    def input(self, **kwargs):
        if self.filename:
            # TODO: work out dependency graph instead of list
            modules = self.resolve_dependencies(self.get_template_dependencies())
            bundle = self.get_bundle(modules)
            bundle_path = self.write_output(bundle, 'bundle.js')
            with open(self.filename, 'r') as f:
                require_content = f.read()
            return """
            var require = {
                baseUrl: "{static_root}",
                bundles: {
                    '{bundle_path}': {modules}
                }
            };
            {require}
            """.format(
                static_root=settings.STATIC_ROOT,
                bundle_path=bundle_path,
                modules=json.dumps([m for m in modules]),
                require=require_content
            )
        else:
            raise NotImplementedError
