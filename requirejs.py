import json
import os
import re
import json

from django.conf import settings
from django.template.loaders.app_directories import app_template_dirs

from compressor.filters.base import FilterBase


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

    def get_require_modules(self):
        require_pattern = re.compile(r'require\((\[.*\])')

        modules = set()
        for template in self.get_template_files():
            f = open(template, 'r')
            matches = require_pattern.findall(f.read(), re.MULTILINE)
            for match in matches:
                # XXX this could use some love
                deps = json.loads(match.replace("'", '"'))
                modules.update(deps)

        # TODO: read modules to make dependency graph

        print(modules)

    def input(self, **kwargs):
        if self.filename:
            print(self.get_require_modules())

            return 'console.log("{}");'.format(self.filename)
        else:
            raise Exception("Should not get here")
