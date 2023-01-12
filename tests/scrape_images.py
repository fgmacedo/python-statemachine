import importlib
import re

from statemachine.contrib.diagram import DotGraphMachine
from statemachine.factory import StateMachineMetaclass


class MachineScraper(object):
    """Scrapes images of the statemachines defined into the examples for the gallery"""

    re_machine_module_name = re.compile(r"python-statemachine/(.*).py$")
    re_replace_png_extension = re.compile(r"\.png$")

    def __init__(self):
        self.seen = set()

    def __repr__(self):
        return "MachineScraper"

    def __call__(self, block, block_vars, gallery_conf):
        # Find all PNG files in the directory of this example.
        from sphinx_gallery.scrapers import figure_rst

        src_file = block_vars["src_file"]

        module_name = self.re_machine_module_name.findall(src_file)
        if len(module_name) != 1:
            return ""

        module_name = module_name[0].replace("/", ".")
        module = importlib.import_module(module_name)

        image_names = []
        image_path_iterator = block_vars["image_path_iterator"]
        for key, value in module.__dict__.items():
            if key.startswith("__"):
                continue

            if not isinstance(value, StateMachineMetaclass) or value._abstract:
                continue

            unique_key = "{}.{}".format(module_name, key)

            if unique_key in self.seen:
                continue
            self.seen.add(unique_key)

            image_path = image_path_iterator.next()
            image_path = self.re_replace_png_extension.sub(".svg", image_path)
            image_names.append(image_path)

            svg = DotGraphMachine(value).get_graph().create_svg().decode()
            with open(image_path, "w") as f:
                f.write(svg)

        # Use the `figure_rst` helper function to generate rST for image files
        return figure_rst(image_names, gallery_conf["src_dir"])
