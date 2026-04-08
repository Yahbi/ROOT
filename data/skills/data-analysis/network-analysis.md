---
name: Network Analysis
description: Centrality measures, community detection, influence propagation, and graph-based analytics
version: "1.0.0"
author: ROOT
tags: [data-analysis, networks, graphs, centrality, community-detection]
platforms: [all]
---

# Network Analysis

Model and analyze relational data structures to identify influential nodes, communities, and information flow patterns.

## Centrality Measures

### Degree Centrality
- **Formula**: `C_D(v) = degree(v) / (n - 1)` where n = number of nodes
- **Interpretation**: Most connected nodes; hub identification
- **In-degree vs out-degree**: For directed graphs; high in-degree = popular/influential; high out-degree = active/broadcaster
- **Limitation**: Ignores position in network; a node with many weak ties may rank higher than one with few critical ties

### Betweenness Centrality
- **Formula**: `C_B(v) = SUM(sigma_st(v) / sigma_st)` over all pairs s,t where sigma_st = shortest paths, sigma_st(v) = those through v
- **Interpretation**: Broker/bridge nodes controlling information flow between communities
- **Computational cost**: O(n * m) for unweighted; use approximation (sampling) for graphs > 100K nodes
- **Application**: Identify critical infrastructure nodes whose removal fragments the network

### Eigenvector Centrality
- **Formula**: `C_E(v) = (1/lambda) * SUM(A_vu * C_E(u))` where A = adjacency matrix, lambda = largest eigenvalue
- **Interpretation**: Being connected to important nodes makes you important (recursive definition)
- **PageRank variant**: `PR(v) = (1-d)/n + d * SUM(PR(u)/out_degree(u))` with damping factor d = 0.85
- **Application**: Ranking web pages, academic papers, influential investors in trading networks

### Closeness Centrality
- **Formula**: `C_C(v) = (n-1) / SUM(d(v,u))` where d = shortest path distance
- **Interpretation**: Average proximity to all other nodes; fast information access
- **Limitation**: Undefined for disconnected graphs; use harmonic closeness as alternative

## Community Detection

### Modularity-Based Methods
- **Modularity**: `Q = (1/2m) * SUM((A_ij - k_i*k_j/2m) * delta(c_i, c_j))`; measures density of within-community edges
- **Louvain algorithm**: Greedy modularity optimization; O(n log n); handles million-node graphs
- **Leiden algorithm**: Improved Louvain with guaranteed connected communities; preferred for production use
- **Resolution parameter**: Higher resolution = more/smaller communities; default gamma = 1.0

### Other Methods
- **Label propagation**: Fast O(m) but non-deterministic; good for very large graphs as initial exploration
- **Spectral clustering**: Use eigenvectors of graph Laplacian; choose k communities via eigengap heuristic
- **Stochastic Block Model (SBM)**: Probabilistic generative model; can detect assortative and disassortative communities
- **Overlapping communities**: Nodes can belong to multiple communities; use CONGA, DEMON, or BigCLAM

## Influence Propagation Models

### Independent Cascade Model
- **Mechanism**: Active node activates each neighbor with probability p (single chance per edge)
- **Influence maximization**: Find k seed nodes to maximize expected total activations (NP-hard; use greedy with lazy evaluation)
- **Application**: Viral marketing, information spread, contagion modeling

### Linear Threshold Model
- **Mechanism**: Node activates when fraction of active neighbors exceeds personal threshold
- **Threshold distribution**: Usually uniform [0,1]; domain-specific calibration improves accuracy
- **Application**: Technology adoption, opinion formation, cascading failures

### Practical Metrics
- **Cascade size**: Average number of nodes activated from a seed; measure of influence potential
- **Cascade depth**: Number of hops from seed to last activation; measures persistence of spread
- **Virality**: `R0 = avg_new_activations_per_active_node`; R0 > 1 = viral growth; R0 < 1 = decay

## Network Metrics for Portfolios

- **Stock correlation network**: Nodes = stocks, edges = correlation > threshold; community = sector
- **Systemic risk**: Betweenness centrality of financial institutions; high betweenness = too-interconnected-to-fail
- **Contagion modeling**: Simulate credit event propagation through interbank lending network
- **Supply chain network**: Map supplier-buyer relationships; identify critical single points of failure
- **Information flow**: Model analyst → fund manager → trader networks; detect information cascade timing

## Tools and Libraries

| Tool | Language | Best For |
|------|----------|----------|
| NetworkX | Python | Analysis, algorithms, small-medium graphs (<100K nodes) |
| igraph | Python/R/C | Fast computation, community detection, million-node graphs |
| graph-tool | Python/C++ | Statistical models (SBM), large-scale analysis |
| Neo4j | Query (Cypher) | Graph database, persistent storage, traversal queries |
| Gephi | GUI | Visualization, exploration, presentation |

## Risk Management

- **Scale limitations**: Most centrality measures are O(n^2) or worse; sample or approximate for large graphs
- **Dynamic networks**: Static analysis on time-evolving networks can be misleading; use temporal network models
- **Edge weight sensitivity**: Results change significantly with weight thresholds; always sensitivity-test the cutoff
- **Missing data**: Network analysis is highly sensitive to missing nodes/edges; acknowledge coverage limitations
- **Interpretation**: High centrality ≠ importance in all contexts; validate against domain knowledge
