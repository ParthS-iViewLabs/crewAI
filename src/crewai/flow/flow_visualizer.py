# flow_visualizer.py

import os

from pyvis.network import Network

from crewai.flow.config import COLORS, NODE_STYLES
from crewai.flow.html_template_handler import HTMLTemplateHandler
from crewai.flow.legend_generator import generate_legend_items_html, get_legend_items
from crewai.flow.utils import calculate_node_levels
from crewai.flow.visualization_utils import (
    add_edges,
    add_nodes_to_network,
    compute_positions,
)


class FlowPlot:
    """Handles the creation and rendering of flow visualization diagrams."""

    def __init__(self, flow):
        """Initialize flow plot with flow instance and styling configuration."""
        self.flow = flow
        self.colors = COLORS
        self.node_styles = NODE_STYLES

    def plot(self, filename):
        """Generate and save interactive flow visualization to HTML file."""
        net = Network(
            directed=True,
            height="750px",
            width="100%",
            bgcolor=self.colors["bg"],
            layout=None,
        )

        # Set options to disable physics
        net.set_options(
            """
            var options = {
                "nodes": {
                    "font": {
                        "multi": "html"
                    }
                },
                "physics": {
                    "enabled": false
                }
            }
        """
        )

        node_levels = calculate_node_levels(self.flow)
        node_positions = compute_positions(self.flow, node_levels)
        add_nodes_to_network(net, self.flow, node_positions, self.node_styles)
        add_edges(net, self.flow, node_positions, self.colors)

        network_html = net.generate_html()
        final_html_content = self._generate_final_html(network_html)

        with open(f"{filename}.html", "w", encoding="utf-8") as f:
            f.write(final_html_content)
        print(f"Plot saved as {filename}.html")

        self._cleanup_pyvis_lib()

    def _generate_final_html(self, network_html):
        """Generate final HTML content with network visualization and legend."""
        current_dir = os.path.dirname(__file__)
        template_path = os.path.join(
            current_dir, "assets", "crewai_flow_visual_template.html"
        )
        logo_path = os.path.join(current_dir, "assets", "crewai_logo.svg")

        html_handler = HTMLTemplateHandler(template_path, logo_path)
        network_body = html_handler.extract_body_content(network_html)

        legend_items = get_legend_items(self.colors)
        legend_items_html = generate_legend_items_html(legend_items)
        final_html_content = html_handler.generate_final_html(
            network_body, legend_items_html
        )
        return final_html_content

    def _cleanup_pyvis_lib(self):
        """Clean up temporary files generated by pyvis library."""
        lib_folder = os.path.join(os.getcwd(), "lib")
        try:
            if os.path.exists(lib_folder) and os.path.isdir(lib_folder):
                import shutil
                shutil.rmtree(lib_folder)
        except Exception as e:
            print(f"Error cleaning up {lib_folder}: {e}")


def plot_flow(flow, filename="flow_plot"):
    """Create and save a visualization of the given flow."""
    visualizer = FlowPlot(flow)
    visualizer.plot(filename)
