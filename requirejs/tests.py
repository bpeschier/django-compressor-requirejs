import django
import unittest

from django.conf import settings
from django.test import SimpleTestCase

# We need to set up a few settings to make sure django-compressor loads
settings.configure(STATIC_ROOT='/tmp/', STATIC_URL='/')

if django.VERSION >= (1, 7):
    django.setup()

from requirejs.finder import ModuleFinder
from requirejs.filter import RequireJSCompiler


class RequireDiscoverTests(SimpleTestCase):
    finder = ModuleFinder(tuple(), None)  # We don't need all the get-module-from-disk features
    pattern_call = 'require'

    def test_spaceless(self):
        modules = self.finder.get_dependencies("""{}(['dep1'], function() {{}});""".format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

        modules = self.finder.get_dependencies("""
        {}(['dep1'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

        # Two dependencies
        modules = self.finder.get_dependencies("""
        {}(['dep1','dep2'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1', 'dep2'], list(modules))

        # Broken call should mean no dependencies
        modules = self.finder.get_dependencies("""
        {}(a['dep1'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual([], list(modules))

    def test_whitespace(self):
        modules = self.finder.get_dependencies("""
        {}( [ 'dep1' ] , function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_multiline_bracket_same(self):
        # Multiline, bracket on same line
        modules = self.finder.get_dependencies("""
        {}([
            'dep1'
            ], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_multiline_bracket_other(self):
        # Multiline, bracket on other line
        modules = self.finder.get_dependencies("""
        {}(
            ['dep1'],
            function() {{}}
        );
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_quotes(self):
        # Single or double should not matter
        modules = self.finder.get_dependencies("""
        {}(['dep1',"dep2"], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1', 'dep2'], list(modules))

        # Misaligned should fail
        modules = self.finder.get_dependencies("""
        {}(["dep1','dep2"], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual([], list(modules))

    def test_greedyness(self):
        # Single or double should not matter
        modules = self.finder.get_dependencies("""
        {}(['dep'], function(Dep) {{
            return Dep.getThingie()[0];
        }});
        """.format(self.pattern_call))
        self.assertListEqual(['dep'], list(modules))

    def test_comments(self):
        # Comments should not matter
        modules = self.finder.get_dependencies("""
        {}(
            [
                'dep1',
                //'dep2'
            ],
            function() {{}}
        );
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_dynamic(self):
        # Dynamic dependencies will not get picked up,
        # but should not raise an error
        modules = self.finder.get_dependencies("""
        {}(
            [
                dep_var1,
                'dep_string',
                dep_var2
            ],
            function() {{}}
        );
        """.format(self.pattern_call))
        self.assertListEqual(['dep_string'], list(modules))

    def test_prefixes(self):
        # Require should not be triggered when we
        # do not actually call it
        modules = self.finder.get_dependencies("""
        some_other_{}(['dep1'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual([], list(modules))

        # Some prefixed are allowed though, since they
        # are new statements
        modules = self.finder.get_dependencies("""
        <script>{}(['dep'], function(Dep) {{
            return new Dep().getThingie()[0];
        }});
        """.format(self.pattern_call))
        self.assertListEqual(['dep'], list(modules))

        modules = self.finder.get_dependencies("""
        ;{}(['dep'], function(Dep) {{
            return Dep.getThingie()[0];
        }});
        """.format(self.pattern_call))
        self.assertListEqual(['dep'], list(modules))

        modules = self.finder.get_dependencies("""
        ;{}(['dep'], function(Dep) {{
            return Dep.getThingie()[0];
        }});
        """.format(self.pattern_call))
        self.assertListEqual(['dep'], list(modules))


# Do everything for define as well
class DefineDiscoverTests(RequireDiscoverTests):
    pattern_call = 'define'


class BundleTests(SimpleTestCase):
    compiler = RequireJSCompiler('')

    def test_bundle_content(self):
        content = """
        define(['other/dep'], function(Dep) {
            return new Dep().test();
        });
        """
        bundle = self.compiler.get_bundle_content('dep', content)
        self.assertEqual(bundle, """
        define("dep", ['other/dep'], function(Dep) {
            return new Dep().test();
        });
        """)


if __name__ == '__main__':
    unittest.main()
