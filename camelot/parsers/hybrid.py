# -*- coding: utf-8 -*-

import logging
import os

from .lattice import Lattice
from .stream import Stream

from .base import BaseParser
from ..core import Table
# from ..utils import (
#     scale_image,
#     scale_pdf,
#     segments_in_bbox,
#     text_in_bbox,
#     merge_close_lines,
#     get_table_index,
#     compute_accuracy,
#     compute_whitespace,
# )
from ..utils import segments_in_bbox


logger = logging.getLogger("camelot")


class Hybrid(BaseParser):

    def __init__(self, *args, **kwargs):
        # TODO: probably need to filter the kwargs
        self.lattice = Lattice(**kwargs)
        self.stream = Stream(**kwargs)

    def extract_tables(self, filename, suppress_stdout=False, layout_kwargs={}):
        self._generate_layout(filename, layout_kwargs)
        if self._log_and_warn(suppress_stdout):
            return []

        for attr in ('rootname', 'filename', 'pdf_width', 'pdf_height', 'horizontal_text', 'vertical_text'):
            setattr(self.lattice, attr, getattr(self, attr))
        self.lattice._generate_image()
        self.lattice._generate_table_bbox()

        _tables = []

        if self.lattice.horizontal_segments and self.lattice.vertical_segments:
            self.table_bbox = self.lattice.table_bbox

            # sort tables based on y-coord
            for table_idx, tk in enumerate(
                sorted(self.table_bbox.keys(), key=lambda x: x[1], reverse=True)
            ):
                cols, rows, v_s, h_s = self.lattice._generate_columns_and_rows(table_idx, tk)
                table = self.lattice._generate_table(table_idx, cols, rows, v_s=v_s, h_s=h_s)
                table._bbox = tk
                _tables.append(table)

        else:
            for attr in ('rootname', 'filename', 'pdf_width', 'pdf_height', 'horizontal_text', 'vertical_text'):
                setattr(self.stream, attr, getattr(self, attr))
            self.stream._generate_table_bbox()
            self.table_bbox = self.stream.table_bbox
            for attr in ('vertical_segments', 'horizontal_segments'):
                setattr(self.stream, attr, getattr(self.lattice, attr))

            if not self.lattice.vertical_segments:  # case for 185_Fox
                h_s = self.lattice.horizontal_segments

                # sort tables based on y-coord
                for table_idx, tk in enumerate(
                    sorted(self.table_bbox.keys(), key=lambda x: x[1], reverse=True)
                ):
                    cols, rows = self.stream._generate_columns_and_rows(table_idx, tk)
                    table = self.stream._generate_table(table_idx, cols, rows)
                    table._bbox = tk
                    _tables.append(table)

            elif not self.lattice.horizontal_segments:  # not implemented
                pass

            else:
                # sort tables based on y-coord
                for table_idx, tk in enumerate(
                    sorted(self.table_bbox.keys(), key=lambda x: x[1], reverse=True)
                ):
                    cols, rows = self.stream._generate_columns_and_rows(table_idx, tk)
                    table = self.stream._generate_table(table_idx, cols, rows)
                    table._bbox = tk
                    _tables.append(table)

        return _tables

