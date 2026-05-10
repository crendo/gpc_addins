import networkx as nx

# 1. Define piping connections (pipe_name, start_node, end_node)
# This represents a simple network:
# a --> d --> e
# b --> a
# c --> d
# d --> f
piping_data = [
    ('P1', 'A', 'D'),
    ('P2', 'B', 'A'),
    ('P3', 'C', 'D'),
    ('P4', 'D', 'E'),
    ('P5', 'D', 'F'),
]

# 2. Create a directed graph to represent the network
G = nx.DiGraph()

# 3. Add pipes as edges, which automatically adds nodes
for pipe, start, end in piping_data:
    G.add_edge(start, end, pipe_id=pipe)

# 4. Enumerate/Number the nodes
node_mapping = {node: i + 1 for i, node in enumerate(G.nodes())}

# 5. Relabel nodes with numbers
H = nx.relabel_nodes(G, node_mapping)

# Print results
print("Node Mapping (Name: ID):", node_mapping)
print("Numbered Edges:", list(H.edges(data=True)))
