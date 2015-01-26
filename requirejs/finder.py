import os
import re
from itertools import chain
from collections import namedtuple

from .utils import is_app_installed


require_pattern = re.compile(r'(?:;|\s|>|^)require\s*\(\s*?(\[[^\]]*\])')
define_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?(\[[^\]]*\])')
define_noargs_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?function')
define_named_pattern = re.compile(r'(?:;|\s|>|^)define\s*\(\s*?(?:((?:"[^"]*")|(?:\'[^\']*\'))\s*?,\s*?)(\[[^\]]*\])?')

Module = namedtuple('Module', ['id', 'location', 'dependencies', 'named'])


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

    @property
    def modules(self):
        """
        Main function to query for modules in Django project
        """
        starting_modules = self.get_template_dependencies()
        if self.starting_dependencies:
            starting_modules = chain(self.starting_dependencies, starting_modules)

        return self.get_modules_from(starting_modules)

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

    def get_module_path(self, module_id):
        """
        Locate a static file for a RequireJS module name.
        """
        # Check if we have an alias for this module
        if self.aliases and module_id in self.aliases:
            module_id = self.aliases[module_id]

        module_js = '{}.js'.format(module_id)

        path = self.static_finder.find(module_js)

        # Check for app alias if we cannot find it
        module_parts = module_js.split('/')
        if path is None and self.app_alias and is_app_installed(module_parts[0]):
            module_parts.insert(1, self.app_alias)
            path = self.static_finder.find('/'.join(module_parts))

        return path

    #
    # Module discovery
    #

    def get_modules_from_id(self, module_id):

        # Clean up the module name, it might contain an argument (!..)
        module_id = self.get_module_name(module_id)

        # Treat the id as path and try to find it
        path = self.get_module_path(module_id)

        if path is not None:
            content = self.get_module_content(path)
            return self.extract_modules(module_id, content)

        return []

    def extract_modules(self, module_id, content):
        dependencies = []
        # First, find declared require-dependencies
        for match in require_pattern.findall(content):
            dependencies.extend(self.get_dependencies_from_match(match))

        # Second, extract all dependencies in define-calls
        for match in define_pattern.findall(content):
            dependencies.extend(self.get_dependencies_from_match(match))

        # Convert the define calls into modules
        for _ in chain(define_pattern.findall(content), define_noargs_pattern.findall(content)):
            yield Module(id=module_id, location=module_id, dependencies=dependencies, named=False)

        # Named modules get special treatment
        for match in define_named_pattern.findall(content):
            defined_id = match[0][1:-1].strip()
            yield Module(id=defined_id, location=module_id, dependencies=dependencies, named=True)

    #
    # Dependency discovery
    #

    def get_template_dependencies(self):
        """
        Walk through templates defined in the project and find require() calls
        """
        dependencies = set()
        for template in self.get_template_files():
            with open(template, 'r') as f:
                for match in require_pattern.findall(f.read()):
                    dependencies.update(self.get_dependencies_from_match(match))
        return dependencies

    def get_modules_from(self, module_ids, known=None):
        """
        Recursively walk through modules and find their dependencies.
        """
        if known is None:
            known = []
        known_ids = [m.id for m in known]

        for module_id in [m_id for m_id in module_ids if m_id not in known_ids]:
            modules = list(self.get_modules_from_id(module_id))
            known.extend(modules)  # TODO: filter out doubles
            for module in modules:
                # Fetch all module's dependencies
                self.get_modules_from(module.dependencies, known=known)
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
    def get_module_content(path):
        with open(path, 'r') as f:
            return f.read()

    @staticmethod
    def get_dependencies_from_match(match):
        """
        Resolve dependencies from the regex match found in a require() or define() call
        """

        dependencies = match[-1] if isinstance(match, tuple) else match

        # Remove list brackets and strip all whitespace
        items = [m.strip() for m in dependencies.strip()[1:-1].split(",")]

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