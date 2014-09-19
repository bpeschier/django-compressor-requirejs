================
django-requirejs
================

Precompiler for Django Compressor to integrate requirejs-modules into bundles.

Installation
~~~~~~~~~~~~

Starting from a Django project with `django-compressor <https://github.com/django-compressor/django-compressor/>`_ set up::

 pip install git+https://github.com/bpeschier/django-requirejs.git

and add requirejs.RequireJSCompiler to your COMPRESS_PRECOMPILERS setting::

 COMPRESS_PRECOMPILERS = (
     ('text/requirejs', 'requirejs.RequireJSCompiler'),
 )

You can now use the content type text/requirejs on your main RequireJS script tag::

 {% compress js %}
     <script type="text/requirejs" src="{% static "website/js/libs/require.min.js" %}"></script>
 {% endcompress %}


The library will by default generate a single bundle with all modules found in templates
and their dependencies. Dynamic dependencies will not be found. It also sets the ``baseUrl``
to your ``STATIC_URL`` and adds aliases for all Django apps installed.

If ``COMPRESS_ENABLED`` is ``False``, only the config will be added and RequireJS will load
modules one by one, without bundles.

Settings
~~~~~~~~

``REQUIREJS_PATHS`` is a dict in the same style as the RequireJS path config. This can be used for example
to make jQuery available in the main namespace (``"jQuery": "<some path>/jquery"``).

``REQUIREJS_BUNDLES`` is a dict to specify which modules get bundled together::

 REQUIRE_BUNDLES = {
    'abovethefold': ['website/awesome', 'website/evenmoreawesome'],
 }

