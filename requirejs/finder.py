import os
import re
from itertools import chain

from .utils import is_app_installed


require_pattern = re.compile(r'(?:;|\s|>|^)require\s*\(\s*?(\[[^\]]*\])')
define_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?(\[[^\]]*\])')
define_named_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?(("[^"]*")|(\'[^\']*\'))\s*?,\s*?(\[[^\]]*\])')


class ModuleFinder(object):
    """
    Find RequireJS modules in a Django project
    """

    def __init__(self, template_directories, static_finder,
                 app_alias=None, starting_dependencies=None, aliases=None):
        self.template_directories = template_directories
        self.static_finder = static_finder
        self.app_alias = app_alias
        self.starting_dependencies = starting_dependencies
        self.aliases = aliases

    #
    # File discovery
    #

    def get_modules(self):
        """
        Main function to query for modules in Django project
        """
        starting_modules = self.get_template_dependencies()
        if self.starting_dependencies:
            starting_modules = chain(self.starting_dependencies, starting_modules)

        return self.resolve_dependencies(starting_modules)

    def get_template_files(self):
        """
        Quick and simple template discovery for TEMPLATE_DIRS and app-based template dirs
        """
        template_files = []
        for template_dir in self.template_directories:
            for directory, dir_names, file_names in os.walk(template_dir):
                for filename in file_names:
                    template_files.append(os.path.join(directory, filename))
        return template_files

    def find_module(self, name):
        """
        Locate a static file for a RequireJS module name.
        """
        module_js = '{}.js'.format(name)

        path = self.static_finder.find(module_js)

        # Check for app alias if we cannot find it
        module_parts = module_js.split('/')
        if path is None and self.app_alias and is_app_installed(module_parts[0]):
            module_parts.insert(1, self.app_alias)
            path = self.static_finder.find('/'.join(module_parts))

        return path

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

        for module in modules:
            # Check if we have an alias for this module
            if self.aliases and module in self.aliases:
                module = self.aliases[module]

            # Clean up the module name, it might contain an argument (!..)
            module = self.get_module_name(module)

            if module not in known:
                path = self.find_module(module)
                if path:  # only continue if we find the module on disk
                    known.add(module)
                    # Fetch all module's dependencies
                    known.update(self.resolve_dependencies(self.get_module_dependencies(path), known=known))
        return known

    #
    # Helpers
    #

    @staticmethod
    def get_module_name(name):
        """
        Strip arguments from module name.
        """
        return name.split('!')[0]

    @staticmethod
    def get_dependencies_from_match(match):
        """
        Resolve dependencies from the regex match found in a require() or define() call
        """
        # Remove list brackets and strip all whitespace
        items = [m.strip() for m in match.strip()[1:-1].split(",")]

        # Remove commented out items and filter out non-string values. We will not raise
        # an error since it might be a dynamic dependency.
        items = [
            i for i in items if
            not i.startswith("//")
            and len(i) > 1
            and i[0] == i[-1]
            and i[0] in ["'", '"']
        ]

        # Strip the quotes
        items = [i[1:-1] for i in items]

        return items