=========
Changelog
=========

0.4 (2014/12/..)
~~~~~~~~~~~~~~~~
* Respect data-main as a dependency.
* Allow bundles to be included in the main library JavaScript file via the REQUIREJS_INCLUDE_MAIN_BUNDLE setting.

0.3 (2014/11/09)
~~~~~~~~~~~~~~~~
* Split up the logic since it was becoming a rather large class with a lot of methods.
* Parsing of the dependency list has gotten some love.
* Actually write the compressed output instead of the uncompressed output.

0.2 (2014/9/29)
~~~~~~~~~~~~~~~
* Made improvements to the parsing patterns for define() and require().

0.1 (2014/9/20)
~~~~~~~~~~~~~~~
* Initial release.