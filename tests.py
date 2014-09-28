import django
from django.conf import settings
from django.test import SimpleTestCase

# We need to set up a few settings to make sure django-compressor loads
settings.configure(STATIC_ROOT='/tmp/', STATIC_URL='/')

if django.VERSION >= (1, 7):
    django.setup()

from requirejs import RequireJSCompiler


class RequireTests(SimpleTestCase):
    compiler = RequireJSCompiler('')
    pattern_call = 'require'

    def test_spaceless(self):
        modules = self.compiler.get_dependencies("""
        {}(['dep1'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

        # Two dependencies
        modules = self.compiler.get_dependencies("""
        {}(['dep1','dep2'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1', 'dep2'], list(modules))

        # Broken call should mean no dependencies
        modules = self.compiler.get_dependencies("""
        {}(a['dep1'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual([], list(modules))

        # Require should not be triggered when we
        # do not actually call it
        modules = self.compiler.get_dependencies("""
        some_other_{}(['dep1'], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual([], list(modules))

    def test_whitespace(self):
        modules = self.compiler.get_dependencies("""
        {}( [ 'dep1' ] , function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_multiline_bracket_same(self):
        # Multiline, bracket on same line
        modules = self.compiler.get_dependencies("""
        {}([
            'dep1'
            ], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_multiline_bracket_other(self):
        # Multiline, bracket on other line
        modules = self.compiler.get_dependencies("""
        {}(
            ['dep1'],
            function() {{}}
        );
        """.format(self.pattern_call))
        self.assertListEqual(['dep1'], list(modules))

    def test_quotes(self):
        # Single or double should not matter
        modules = self.compiler.get_dependencies("""
        {}(['dep1',"dep2"], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1', 'dep2'], list(modules))

        # Misaligned should fail in JS, but we will allow it
        # to simplify parsing
        modules = self.compiler.get_dependencies("""
        {}(["dep1','dep2"], function() {{}});
        """.format(self.pattern_call))
        self.assertListEqual(['dep1', 'dep2'], list(modules))


# Do everything for define as well
class DefineTests(RequireTests):
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