import os
import re

from statemachine.contrib.diagram import DotGraphMachine
from statemachine.factory import StateMachineMetaclass

from .helpers import import_module_by_path


class MachineScraper:
    """Scrapes images of the statemachines defined into the examples for the gallery"""

    re_replace_png_extension = re.compile(r"\.png$")

    def __init__(self, project_root):
        self.project_root = project_root
        sanitized_path = re.escape(os.path.abspath(self.project_root))
        self.re_machine_module_name = re.compile(f"{sanitized_path}/(.*)\\.py$")
        self.seen = set()

    def __repr__(self):
        return "MachineScraper"

    def _get_module(self, src_file):
        module_name = self.re_machine_module_name.findall(src_file)
        if len(module_name) != 1:
            return

        return import_module_by_path(module_name[0])

    def generate_image(self, sm_class, original_path):
        image_path = self.re_replace_png_extension.sub(".svg", original_path)

        svg = DotGraphMachine(sm_class).get_graph().create_svg().decode()
        with open(image_path, "w") as f:
            f.write(svg)
        return image_path

    def __call__(self, block, block_vars, gallery_conf):
        "Find all PNG files in the directory of this example."
        from sphinx_gallery.scrapers import figure_rst

        module = self._get_module(block_vars["src_file"])
        if module is None:
            return ""

        image_names = []
        image_path_iterator = block_vars["image_path_iterator"]
        for key, value in module.__dict__.items():
            unique_key = f"{module.__name__}.{key}"

            if (
                key.startswith("__")
                or unique_key in self.seen
                or not isinstance(value, StateMachineMetaclass)
                or value._abstract
            ):
                continue

            self.seen.add(unique_key)
            image_names.append(self.generate_image(value, image_path_iterator.next()))

        # Use the `figure_rst` helper function to generate rST for image files
        return figure_rst(image_names, gallery_conf["src_dir"])
