from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from containernet_code.my_topology import TopologyHandler


def plot_topology(log_path: Path, topo_handler: TopologyHandler):
    """Visualize the Mininet topology using NetworkX and Matplotlib"""
    G = nx.Graph()

    for host in topo_handler.fl_clients:
        G.add_node(host, type='FL')

    for host in topo_handler.bg_clients:
        G.add_node(host, type='BG')

    for switch in topo_handler.topo.switches():
        G.add_node(switch, type='SW')

    G.add_node(topo_handler.fl_server, type='FLS')

    for src, dst in topo_handler.topo.links():
        G.add_edge(src, dst)

    pos = nx.spring_layout(G, seed=42)  # Layout can be changed

    node_options = {
        'FL': {'shape': 'o', 'color': 'lightblue', 'size': 1000},
        'BG': {'shape': 'p', 'color': 'lightgreen', 'size': 500},
        'SW': {'shape': 's', 'color': 'orange', 'size': 600},
        'FLS': {'shape': 'o', 'color': 'dodgerblue', 'size': 1000}
    }

    num_edges = len(G.edges)
    fig_size = max(5,  num_edges // 4)  # Example scaling
    plt.figure(figsize=(fig_size, fig_size))

    for node_type, opts in node_options.items():
        nodes = [n for n in G.nodes if G.nodes[n]['type'] == node_type]
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=nodes,
            node_color=opts['color'],
            node_shape=opts['shape'],
            node_size=opts['size']
        )

    nx.draw_networkx_edges(G, pos)
    nx.draw_networkx_labels(G, pos, font_size=10)

    plt.title("Mininet Topology")
    plt.savefig(log_path / "topology.png", dpi=300, bbox_inches='tight')
