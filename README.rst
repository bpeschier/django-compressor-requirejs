===========================
django-compressor-requirejs
===========================

Precompiler for `django-compressor <https://github.com/django-compressor/django-compressor/>`_ to integrate
`RequireJS <http://requirejs.org>`_-modules into `bundles <http://requirejs.org/docs/api.html#config-bundles>`_.

This library does not use the `r.js <https://github.com/jrburke/r.js>`_ compressor, but instead collects the
dependencies from your templates and resolves them into bundles, letting django-compressor do the compressing.

Installation
~~~~~~~~~~~~

First, `install django-compressor <http://django-compressor.readthedocs.org/en/latest/quickstart/#installation>`_
into your Django project and configure it. Then install django-compressor-requirejs::

 pip install django-compressor-requirejs

and add ``requirejs.RequireJSCompiler`` to your ``COMPRESS_PRECOMPILERS`` setting::

 COMPRESS_PRECOMPILERS = (
     ('text/requirejs', 'requirejs.RequireJSCompiler'),
 )

You can now use the content type text/requirejs on your main RequireJS script tag::

 {% compress js %}
     <script type="text/requirejs" src="{% static "website/js/libs/require.min.js" %}"></script>
 {% endcompress %}

The library will by default generate a single bundle with all modules found in templates
and their dependencies. Dynamic dependencies will not be found. It also sets the ``baseUrl``
to your ``STATIC_URL``.

If ``COMPRESS_ENABLED`` is ``False``, only the config will be added and RequireJS will load
modules one by one, without bundles.

Settings
~~~~~~~~

You can control RequireJS with three options:

``REQUIREJS_PATHS`` is a dict in the same style as the RequireJS path config. This can be used for example
to make jQuery available in the main namespace (``"jquery": "<some path>/jquery.min"``).

``REQUIREJS_BUNDLES`` is a dict to specify which modules get bundled together::

 REQUIREJS_BUNDLES = {
    'abovethefold': ['website/awesome', 'website/evenmoreawesome'],
 }

Every module not mentioned in this setting will end up in the ``main`` catch-all bundle.

``REQUIREJS_APP_ALIAS`` (default ``None``) allows the Javascript directory inside your static root to be addressed by
just the app name. Require/define calls to ``website/some_module`` will be searched as
``{{ STATIC_URL }}/website/<alias>/some_module.js`` if not found in ``{{ STATIC_URL }}/website/``.

Under the hood
~~~~~~~~~~~~~~

django-compressor-requirejs makes use of RequireJS's ``bundles`` configuration option, making it possible to bundle
modules together and let RequireJS fetch the bundle when it needs one of the modules. The philosophy is that modules
bundled together are really often used together, which lowers the amount of requests the browser has to do.

It uses the filter mechanism in django-compressor on the script tag used to load RequireJS itself, injecting a
configuration pointing RequireJS to ``STATIC_URL`` and -- if compression is enabled -- the compressed bundle(s).

Discovery of modules is done by searching all template directories for calls to RequireJS and parsing their
dependencies. This is a plain text search, no real parsing of Javascript or HTML is done (similar to ``makemessages``).
All found modules are then similarly scanned for their dependencies.

Since no parsing or evaluation is done, any dynamic loading of dependencies with variables is not supported. If you
want to let django-compressor-requirejs pick it up, annotate the require() call with all options (if feasible, of
course).


So django-require and compressor_requirejs exist.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes, they do; and if you want to use the (otherwise excellent) r.js compressor with django-compressor, please take a
look at  `compressor_requirejs <https://github.com/dresiu/compressor_requirejs>`_. And if you do not use
django-compressor, visit etianen's `django-require <https://github.com/etianen/django-require>`_.
