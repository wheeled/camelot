# -*- coding: utf-8 -*-

import logging
import os
import pandas as pd
import warnings

from ..utils import (
    compute_accuracy,
    compute_whitespace,
    get_page_layout,
    get_table_index,
    get_text_objects,
    segments_in_bbox,
    text_in_bbox,
)

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

    def _update_attributes(self, table_idx, table):
        pos_errors = []
        # TODO: have a single list in place of two directional ones?
        # sorted on x-coordinate based on reading order i.e. LTR or RTL
        for direction in ["vertical", "horizontal"]:
            for t in self.t_bbox[direction]:
                indices, error = get_table_index(
                    table,
                    t,
                    direction,
                    split_text=self.split_text,
                    flag_size=self.flag_size,
                    strip_text=self.strip_text,
                )
                if indices[:2] != (-1, -1):
                    pos_errors.append(error)
                    if hasattr(self, '_reduce_index'):
                        indices = self.__class__._reduce_index(
                            table, indices, shift_text=self.shift_text
                        )
                    for r_idx, c_idx, text in indices:
                        table.cells[r_idx][c_idx].text = text
        accuracy = compute_accuracy([[100, pos_errors]])

        if hasattr(self, 'copy_text') and self.copy_text is not None:
            table = self.__class__._copy_spanning_text(table, copy_text=self.copy_text)

        data = table.data
        table.df = pd.DataFrame(data)
        table.shape = table.df.shape

        whitespace = compute_whitespace(data)
        table.flavor = self.__class__.__name__.lower()
        table.accuracy = accuracy
        table.whitespace = whitespace
        table.order = table_idx + 1
        table.page = int(os.path.basename(self.rootname).replace("page-", ""))

        # for plotting
        _text = []
        _text.extend([(t.x0, t.y0, t.x1, t.y1) for t in self.horizontal_text])
        _text.extend([(t.x0, t.y0, t.x1, t.y1) for t in self.vertical_text])
        table._text = _text
        if table.flavor == 'lattice':
            table._image = (self.image, self.table_bbox_unscaled)
            table._segments = (self.vertical_segments, self.horizontal_segments)
            table._textedges = None
        else:
            table._image = None
            table._segments = None
            table._textedges = self.textedges

        return table

