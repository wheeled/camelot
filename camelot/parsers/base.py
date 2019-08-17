# -*- coding: utf-8 -*-

import logging
import os
import warnings

from ..utils import get_page_layout, get_text_objects, segments_in_bbox, text_in_bbox

logger = logging.getLogger("camelot")


class BaseParser(object):
    """Defines a base parser.
    """

    def _generate_layout(self, filename, layout_kwargs):
        self.filename = filename
        self.layout_kwargs = layout_kwargs
        self.layout, self.dimensions = get_page_layout(filename, **layout_kwargs)
        self.images = get_text_objects(self.layout, ltype="image")
        self.horizontal_text = get_text_objects(self.layout, ltype="horizontal_text")
        self.vertical_text = get_text_objects(self.layout, ltype="vertical_text")
        self.pdf_width, self.pdf_height = self.dimensions
        self.rootname, __ = os.path.splitext(self.filename)

    def _log_and_warn(self, suppress_stdout):
        empty = False
        if not suppress_stdout:
            logger.info("Processing {}".format(os.path.basename(self.rootname)))

        if not self.horizontal_text:
            empty = True
            if self.images:
                warnings.warn(
                    "{} is image-based, camelot only works on"
                    " text-based pages.".format(os.path.basename(self.rootname))
                )
            else:
                warnings.warn(
                    "No tables found on {}".format(os.path.basename(self.rootname))
                )  # TODO: more correctly no TEXT found on page, whether or not a table is found
        return empty

    def _select_table_bbox_elements(self, tk):
        t_bbox = {}
        try:
            v_s, h_s = segments_in_bbox(tk, self.vertical_segments, self.horizontal_segments)
        except AttributeError:
            v_s = h_s = []

        t_bbox["horizontal"] = text_in_bbox(tk, self.horizontal_text)
        t_bbox["vertical"] = text_in_bbox(tk, self.vertical_text)

        t_bbox["horizontal"].sort(key=lambda x: (-x.y0, x.x0))
        t_bbox["vertical"].sort(key=lambda x: (x.x0, -x.y0))

        self.t_bbox = t_bbox

        return v_s, h_s
