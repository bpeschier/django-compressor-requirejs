import re
import json

import django
from django.utils.six import text_type
from django.utils.safestring import mark_safe
from django.core.files.base import ContentFile

# noinspection PyPackageRequirements
from compressor.conf import settings
# noinspection PyPackageRequirements
from compressor.filters.base import FilterBase
# noinspection PyPackageRequirements
from compressor.js import JsCompressor

from .finder import ModuleFinder

define_replace_pattern = re.compile(r'define\s*\(([^\)]*?)\)')

REQUIREJS_PATHS = settings.REQUIREJS_PATHS if hasattr(settings, 'REQUIREJS_PATHS') else {}
REQUIREJS_BUNDLES = settings.REQUIREJS_BUNDLES if hasattr(settings, 'REQUIREJS_BUNDLES') else {}
REQUIREJS_APP_ALIAS = settings.REQUIREJS_APP_ALIAS if hasattr(settings, 'REQUIREJS_APP_ALIAS') else None


class RequireJSCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        self.charset = charset
        self.attrs = attrs
        self.finder = ModuleFinder(REQUIREJS_APP_ALIAS)
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
    # Bundle creation
    #

    @staticmethod
    def get_bundle_content(module, original_content):
        """
        Rewrite the module to include it's module path so it can be included in a bundle
        """
        return define_replace_pattern.sub(
            r'define("{module}", \1)'.format(module=module),
            text_type(original_content),
            re.MULTILINE
        )

    def get_bundle_module(self, module):
        """
        Rewrite a module into a bundle, which means we have to add the name of the module into the define() call
        """
        path = self.finder.find_module(module)
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
        modules = self.finder.get_modules()
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

    #
    # Helper
    #

    @staticmethod
    def get_installed_app_labels():
        if django.VERSION >= (1, 7):
            from django.apps import apps

            return [app.label for app in apps.get_app_configs()]
        else:
            return [app.split('.')[-1] for app in settings.INSTALLED_APPS]
