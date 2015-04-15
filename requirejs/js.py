from django.conf import settings
from django.template import Context
from django.template.loader import render_to_string

from compressor.js import JsCompressor as CompressorJsCompressor
from compressor.base import METHOD_INPUT, SOURCE_FILE, post_compress


class JsCompressor(CompressorJsCompressor):
    def __init__(self, *args, **kwargs):
        super(JsCompressor, self).__init__(*args, **kwargs)
        self.data_attributes = {}

    def hunks(self, forced=False):
        """
        The heart of content parsing, iterates over the
        list of split contents and looks at its kind
        to decide what to do with it. Should yield a
        bunch of precompiled and/or rendered hunks.
        """
        enabled = settings.COMPRESS_ENABLED or forced

        for kind, value, basename, elem in self.split_contents():
            precompiled = False
            attribs = self.parser.elem_attribs(elem)
            charset = attribs.get("charset", self.charset)
            self.data_attributes.update({
                attr: value for (attr, value) in attribs.items()
                if attr.startswith('data-')
            })
            options = {
                'method': METHOD_INPUT,
                'elem': elem,
                'kind': kind,
                'basename': basename,
                'charset': charset,
            }

            if kind == SOURCE_FILE:
                options = dict(options, filename=value)
                value = self.get_filecontent(value, charset)

            if self.all_mimetypes:
                precompiled, value = self.precompile(value, **options)

            if enabled:
                yield self.filter(value, **options)
            else:
                if precompiled:
                    yield self.handle_output(kind, value, forced=True,
                                             basename=basename)
                else:
                    yield self.parser.elem_str(elem)

    def render_output(self, mode, context=None):
        """
        Renders the compressor output with the appropriate template for
        the given mode and template context.
        """
        # Just in case someone renders the compressor outside
        # the usual template rendering cycle
        if 'compressed' not in self.context:
            self.context['compressed'] = {}

        self.context['compressed'].update(context or {})
        self.context['compressed'].update(self.extra_context)

        if self.data_attributes:
            extra = self.context['compressed'].get('extra', "")
            extra += ' '.join(['{}={}'.format(*item) for item in self.data_attributes.items()])
            self.context['compressed']['extra'] = " " + extra.strip()

        final_context = Context(self.context)
        post_compress.send(sender=self.__class__, type=self.type,
                           mode=mode, context=final_context)
        template_name = self.get_template_name(mode)

        return render_to_string(template_name, context_instance=final_context)