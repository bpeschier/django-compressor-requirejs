from copy import deepcopy
from itertools import chain
import re
import json

from django.utils.six import text_type
from django.utils.safestring import mark_safe
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile


# noinspection PyPackageRequirements
from compressor.conf import settings
# noinspection PyPackageRequirements
from compressor.filters.base import FilterBase

from .finder import ModuleFinder
from .utils import get_installed_app_labels, get_app_template_dirs
from .js import JsCompressor

define_replace_pattern = re.compile(r'define\s*\(([^\)]*?)\)')

CONFIG = settings.REQUIREJS_CONFIG if hasattr(settings, 'REQUIREJS_CONFIG') else {}
APP_ALIAS = settings.REQUIREJS_APP_ALIAS if hasattr(settings, 'REQUIREJS_APP_ALIAS') else None
INCLUDE_MAIN_BUNDLE = settings.REQUIREJS_INCLUDE_MAIN_BUNDLE \
    if hasattr(settings, 'REQUIREJS_INCLUDE_MAIN_BUNDLE') else False


class RequireJSCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        self.charset = charset
        self.attrs = attrs

        # Get possible data-main="<module>" from attributes
        main = self.attrs.get("data-main", "").strip() if self.attrs else None
        self.finder = self.get_module_finder(main=main)

        super(RequireJSCompiler, self).__init__(content, filter_type, filename)

    # noinspection PyMethodMayBeStatic
    def get_module_finder(self, main=None):
        template_directories = settings.TEMPLATE_DIRS + get_app_template_dirs()
        shim_dependencies = list(chain(*[s.get('deps', []) for s in CONFIG.get('shim', {}).values()]))
        main_dependency = [main] if main else []
        dependencies = shim_dependencies + main_dependency
        aliases = CONFIG.get('paths', {})
        return ModuleFinder(template_directories, finders,
                            app_alias=APP_ALIAS, starting_dependencies=dependencies, aliases=aliases)

    def input(self, **kwargs):
        if self.filename:
            with open(self.filename, 'r') as f:
                require_content = f.read()
        else:
            require_content = self.content

        config = self.get_default_config()
        if settings.COMPRESS_ENABLED:
            bundles, main_modules = self.get_bundles(skip_main_bundle=INCLUDE_MAIN_BUNDLE)
            if bundles:
                config.update({'bundles': bundles})
            if INCLUDE_MAIN_BUNDLE:  # Add the main bundle to the require content written
                require_content += '\n'.join([self.get_bundle_module(module) for module in main_modules])
        elif 'bundles' in config:
            del config['bundles']  # Only write bundles when we compress

        return text_type("var require = {config};{content}").format(config=json.dumps(config), content=require_content)

    def output(self, **kwargs):
        raise NotImplementedError

    #
    # Bundle creation
    #

    @staticmethod
    def get_bundle_content(module, original_content):
        """
        Rewrite the module to include it's module path so it can be included in a bundle.

        Returns the rewritten content of the module and None if no define-call was found.
        """
        text_content = text_type(original_content, settings.FILE_CHARSET)
        define_call = define_replace_pattern.findall(text_content)
        if define_call:
            if not module.named:
                return define_replace_pattern.sub(
                    r'define("{module}", \1)'.format(module=module.id),
                    text_content,
                    re.MULTILINE
                )
            else:
                return text_content

    def get_bundle_module(self, module):
        """
        Rewrite a module into a bundle, which means we have to add the name of the module into the define() call
        """
        path = self.finder.get_module_path(module.location)
        if not path:
            raise ValueError("Could not find module {} on disk".format(module.id))

        with open(path, 'r') as f:
            bundle_module = self.get_bundle_content(module, f.read())
            if bundle_module is None:
                raise ValueError("Module {} is not an AMD module".format(module.id))
            return bundle_module

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
        filtered = compressor.filter(content, compressor.cached_filters, method='input', kind='js')
        output = compressor.filter_output(filtered)
        path = compressor.get_filepath(output, basename=basename)
        # Write it
        compressor.storage.save(path, ContentFile(output.encode(compressor.charset)))
        return mark_safe(compressor.storage.url(path))

    #
    # RequireJS config generation
    #

    def get_bundles(self, skip_main_bundle=False):
        """
        Generate the ``bundles`` configuration option for RequireJS.

        This will skip configured shims.
        """
        shims = CONFIG.get('shim', {})
        modules = [m for m in self.finder.modules if m.id not in shims]
        bundles = {}
        configured_bundles = CONFIG.get('bundles', {})
        if configured_bundles:
            # Let the configured bundles get generated, leaving the remaining modules for the ``main`` bundle.
            for name, bundle_module_ids in configured_bundles.items():
                bundle_modules = [m for m in modules if m.id in bundle_module_ids]
                bundle_path = self.write_bundle(name, bundle_modules)
                bundles[bundle_path] = [m.id for m in bundle_modules]
                for m in bundle_modules:
                    modules.remove(m)

        # If we still have modules, write them
        if modules or skip_main_bundle:
            bundles[self.write_bundle('main', modules)] = [m.id for m in modules]

        return bundles, modules

    @staticmethod
    def get_default_config():
        """
        Generate a default config for RequireJS setting the ``baseUrl`` to our ``STATIC_URL`` so we can define
        our modules in static, and add, if configured, aliases for all installed apps
        """
        config = deepcopy(CONFIG)

        paths = config.get('paths', {})
        if APP_ALIAS:
            paths.update({
                app: '{app}/{alias}'.format(app=app, alias=APP_ALIAS)
                for app in get_installed_app_labels()
            })

        if paths:
            config['paths'] = paths

        config['baseUrl'] = settings.STATIC_URL
        return config
