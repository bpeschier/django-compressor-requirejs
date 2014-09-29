from itertools import chain
import os
import re
import json

from django.core.files.base import ContentFile
from django.template.loaders.app_directories import app_template_dirs
from django.contrib.staticfiles import finders
import django

# noinspection PyPackageRequirements
from compressor.conf import settings
# noinspection PyPackageRequirements
from compressor.filters.base import FilterBase
# noinspection PyPackageRequirements
from compressor.js import JsCompressor
from django.utils.safestring import mark_safe


require_pattern = re.compile(r'(?:;|\s|>|^)require\s*\(\s*?(\[[^\]]*\])')
define_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?(\[[^\]]*\])')
define_replace_pattern = re.compile(r'define\s*\(([^\)]*?)\)')

REQUIREJS_PATHS = settings.REQUIREJS_PATHS if hasattr(settings, 'REQUIREJS_PATHS') else {}
REQUIREJS_BUNDLES = settings.REQUIREJS_BUNDLES if hasattr(settings, 'REQUIREJS_BUNDLES') else {}
REQUIREJS_APP_ALIAS = settings.REQUIREJS_APP_ALIAS if hasattr(settings, 'REQUIREJS_APP_ALIAS') else None


class RequireJSCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        self.charset = charset
        self.attrs = attrs
        super(RequireJSCompiler, self).__init__(content, filter_type, filename)

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

    #
    # File discovery
    #

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
        if path is None and REQUIREJS_APP_ALIAS and self.is_app_installed(module_parts[0]):
            module_parts.insert(1, REQUIREJS_APP_ALIAS)
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

    @staticmethod
    def get_installed_app_labels():
        pass
        if django.VERSION >= (1, 7):
            from django.apps import apps

            return [app.label for app in apps.get_app_configs()]
        else:
            return [app.split('.')[-1] for app in settings.INSTALLED_APPS]

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

    #
    # Bundle creation
    #

    @staticmethod
    def get_bundle_content(module, original_content):
        return define_replace_pattern.sub(
            r'define("{module}", \1)'.format(module=module),
            original_content,
            re.MULTILINE
        )

    def get_bundle_module(self, module):
        """
        Rewrite a module into a bundle, which means we have to add the name of the module into the define() call
        """
        path = self.find_module(module)
        if not path:
            raise ValueError("Could not find module {} on disk".format(module))
        with open(path, 'r') as f:
            return self.get_bundle_content(module, f.read())

    def write_bundle(self, basename, modules):
        """
        Let compressor write the bundled modules with a basename.
        """
        bundles = [self.get_bundle_module(module) for module in modules]
        return self.write_output('\n'.join(bundles), '{name}.js'.format(name=basename))

    @staticmethod
    def write_output(content, basename):
        """
        Leverage django-compressor's JsCompressor to write the Javascript, making use of configured filters
        and other settings.
        """
        # Compress it
        compressor = JsCompressor()
        filtered = compressor.filter(content, method='input', kind='js')
        output = compressor.filter_output(filtered)
        path = compressor.get_filepath(output, basename=basename)
        # Write it
        compressor.storage.save(path, ContentFile(content.encode(compressor.charset)))
        return mark_safe(compressor.storage.url(path))

    #
    # RequireJS config generation
    #

    def get_bundle_config(self):
        """
        Generate the ``bundles`` configuration option for RequireJS.
        """
        # TODO: work out dependency graph instead of list? Is this really needed for bundles?
        modules = self.resolve_dependencies(self.get_template_dependencies())

        bundles = {}
        if REQUIREJS_BUNDLES:
            # Let the configured bundles get generated, leaving the remaining modules for the ``main`` bundle.
            for name, bundle_modules in REQUIREJS_BUNDLES.items():
                bundle_path = self.write_bundle(name, bundle_modules)
                bundles[bundle_path] = list(bundle_modules)
                for m in bundle_modules:
                    modules.discard(m)

        # If we still have modules, write them
        if modules:
            bundles[self.write_bundle('main', modules)] = list(modules)

        return {
            'bundles': bundles,
        } if bundles else {}

    def get_default_config(self):
        """
        Generate a default config for RequireJS setting the ``baseUrl`` to our ``STATIC_URL`` so we can define
        our modules in static, and add, if configured, aliases for all installed apps
        """

        paths = {}
        if REQUIREJS_APP_ALIAS:
            paths.update({
                app: '{app}/{alias}'.format(app=app, alias=REQUIREJS_APP_ALIAS)
                for app in self.get_installed_app_labels()
            })

        paths.update(REQUIREJS_PATHS)

        return {
            'baseUrl': settings.STATIC_URL,
            'paths': paths,
        }
