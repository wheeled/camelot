# -*- coding: utf-8 -*-

import os

from ..utils import get_page_layout, get_text_objects


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

    def select_table_bbox_elements(self, tk, vertical_segments, horizontal_segments):
        t_bbox = {}

        v_s, h_s = segments_in_bbox(
            tk, vertical_segments, horizontal_segments
        )

        t_bbox["horizontal"] = text_in_bbox(tk, self.horizontal_text)
        t_bbox["vertical"] = text_in_bbox(tk, self.vertical_text)

        t_bbox["horizontal"].sort(key=lambda x: (-x.y0, x.x0))
        t_bbox["vertical"].sort(key=lambda x: (x.x0, -x.y0))

        self.t_bbox = t_bbox

        return v_s, h_s
