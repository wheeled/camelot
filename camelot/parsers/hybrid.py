# -*- coding: utf-8 -*-

import logging
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os
from PIL import Image

from .lattice import Lattice
from .stream import Stream

from .base import BaseParser
from ..core import BoundingBox
from ..utils import (
    rle,
    # scale_image,
    # scale_pdf,
    # segments_in_bbox,
    # text_in_bbox,
    # merge_close_lines,
    # get_table_index,
    # compute_accuracy,
    # compute_whitespace,
)


logger = logging.getLogger("camelot")


class PseudoImage(object):

    def __init__(self, dimensions):
        self.shape = np.array(dimensions, dtype=np.int16)
        self.limits = (0, 0, *self.shape)
        self.image = self.clear()
        self.horizontal_lines = []
        self.vertical_lines = []

    def clear(self):
        return np.zeros((self.shape[1], self.shape[0]), dtype=np.int8)

    def plot_text(self, textlines, trim=(0, 0)):  #TODO: evaluate suitable defaults for h, v trim
        for tl in textlines:
            if tl.get_text().strip():
                x_span = slice(int(tl.x0) - trim[0], int(tl.x1) + trim[0] + 1)
                y_span = slice(int(tl.y0) - trim[1], int(tl.y1) + trim[1] + 1)
                self.image[y_span, x_span] = 1
        self.image[:, -1] = 1
        self.image[-1, :] = 1

    def scan(self, segment, range):
        segment[0] = 0
        segment[-1] = 1
        bands = rle(segment)[1]
        bands = bands.reshape(len(bands) // 2, 2)
        return [np.average(band) + range[0] for band in bands]

    def scan_2d(self, bbox):
        h_sweep = np.array([
            1 if has_text else 0
            for has_text in np.any(self.image[bbox[1]:bbox[3] + 1, bbox[0]:bbox[2] + 1], axis=0)
        ])
        v_sweep = np.array([
            1 if has_text else 0
            for has_text in np.any(self.image[bbox[1]:bbox[3] + 1, bbox[0]:bbox[2] + 1], axis=1)
        ])
        h_scan = self.scan(h_sweep, (bbox[0], bbox[2] + 1))
        v_scan = self.scan(v_sweep, (bbox[1], bbox[3] + 1))
        return h_scan, v_scan

    def scan_for_tables(self, index_range=None):
        # TODO: [wheeled] can it be made recursive?
        if not index_range:
            index_range = self.limits
        table_candidate = BoundingBox()
        self.tables = []
        for y in range(self.limits[3]):
            row = self.image[y]
            h_breaks = self.scan(self.image[y], (index_range[0], index_range[2]))
            if len(h_breaks) <= 2 and not table_candidate.extent:
                continue  # nothing to see here
            elif len(h_breaks) > 2 and not table_candidate.extent:
                # could be start of a table
                table_candidate.set((h_breaks[0] - 2, y - 2, h_breaks[-1] + 2, y))
            elif len(h_breaks) > 2:
                # could be continuation of a table - extend limits vertically
                table_candidate.encompass(extent=(h_breaks[0], table_candidate.extent[1], h_breaks[-1], y))
            elif len(h_breaks) < 2:
                # could be the gap between rows in the table - extend limits vertically
                table_candidate.encompass(extent=(*table_candidate.extent[:3], y))
            elif h_breaks[0] > table_candidate.extent[0] and h_breaks[-1] < table_candidate.extent[2]:
                # probably a heading - extend limits vertically
                table_candidate.encompass(extent=(*table_candidate.extent[:3], y))
            else:
                # check for end of table
                h, v = self.scan_2d(table_candidate.int_extent)
                if len(v) > 2:
                    # table must have at least 2 rows
                    self.tables.append(table_candidate.extent)
                table_candidate.clear()
        return self.tables
        # TODO: work through the various pdfs to improve the success rate
        # TODO: make the lines
        # TODO: rescan (or recurse) looking for spanned cells
        # TODO: [wheeled] return horizontal segments and vertical segments as well


    def plot(self, base_image):
        # TODO: concept can be ported to plotting
        fig = plt.figure(figsize=tuple(np.array(self.limits[2:]) / 100 * 1.2), dpi=100)
        ax = fig.add_subplot(111, aspect="equal")
        for t in self.tables:
            ax.add_patch(
                patches.Rectangle(
                    (t[0], t[1]), t[2] - t[0], t[3] - t[1], fill=False, color="red"
                )
            )
        ax.imshow(
            base_image, zorder=0, origin='upper',
            extent=(self.limits[0], self.limits[2], self.limits[1], self.limits[3],)
        )
        plt.show()


class Hybrid(BaseParser):

    def __init__(self, *args, **kwargs):
        # TODO: probably need to filter the kwargs
        self.lattice = Lattice(**kwargs)
        self.stream = Stream(**kwargs)

    def _modified_nurminen_table_detection(self, textlines):
        """
        Operates by creating a pseudo image of the page and finding horizontal and vertical lines
        where there is no text.
        """

        # TODO: [wheeled] so far this algo is no better than nurminen:
        # it does produce lists which could be useful to operate as horizontal_segments and vertical_segments in lattice

        self.pseudo_image = PseudoImage(self.dimensions)
        self.pseudo_image.plot_text(self.horizontal_text)
        proforma_bbox = self.pseudo_image.scan_for_tables()
        # TODO: two lines below for development only
        lo_res_img = Image.fromarray(self.lattice.image).resize(np.array(self.dimensions, dtype=np.int16))
        self.pseudo_image.plot(lo_res_img)

        table_bbox = {}
        for bbox in proforma_bbox:
            table_bbox.update({bbox: None})

        if not len(table_bbox):
            table_bbox = {(0, 0, self.pdf_width, self.pdf_height): None}

        return table_bbox

    def _generate_table_bbox(self):
        self.lattice._generate_table_bbox()
        self.horizontal_segments = self.lattice.horizontal_segments
        self.vertical_segments = self.lattice.vertical_segments
        self.table_bbox = self.lattice.table_bbox
        # TODO: line below for development only
        self._modified_nurminen_table_detection(self.horizontal_text)

    def extract_tables(self, filename, suppress_stdout=False, layout_kwargs={}):
        self._generate_layout(filename, layout_kwargs)
        if self._log_and_warn(suppress_stdout):
            return []

        self._generate_image()
        for attr in (
            'rootname', 'filename', 'pdf_width', 'pdf_height', 'horizontal_text', 'vertical_text', 'imagename'
        ):
            setattr(self.lattice, attr, getattr(self, attr))
        self._generate_table_bbox()

        _tables = []

        if self.horizontal_segments and self.vertical_segments:
            # proceed with lattice algorithm
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

            if not self.vertical_segments:  # case for 185_Fox
                h_s = self.lattice.horizontal_segments

                # sort tables based on y-coord
                for table_idx, tk in enumerate(
                    sorted(self.table_bbox.keys(), key=lambda x: x[1], reverse=True)
                ):
                    cols, rows = self.stream._generate_columns_and_rows(table_idx, tk)
                    table = self.stream._generate_table(table_idx, cols, rows)
                    table._bbox = tk
                    _tables.append(table)

            elif not self.horizontal_segments:  # not implemented
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

