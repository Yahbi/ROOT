---
name: Graph Theory
description: Shortest paths, network flow, community detection, PageRank, and graph algorithms for analytical applications
version: "1.0.0"
author: ROOT
tags: [general, graph-theory, algorithms, networks, PageRank]
platforms: [all]
---

# Graph Theory

Apply fundamental graph algorithms to model relationships, optimize routes, identify communities, and rank entities in connected systems.

## Graph Fundamentals

- **Graph G = (V, E)**: V = vertices (nodes), E = edges (connections); |V| = n, |E| = m
- **Directed vs undirected**: Directed edges have source and target; undirected edges are bidirectional
- **Weighted**: Edges carry numerical values (cost, distance, capacity, correlation)
- **Sparse vs dense**: Most real-world graphs are sparse (m << n^2); use adjacency list, not matrix
- **Representations**: Adjacency matrix O(n^2 space), adjacency list O(n+m space), edge list O(m space)
- **Key properties**: Degree distribution, diameter, clustering coefficient, connected components

## Shortest Path Algorithms

### Single-Source Shortest Path
- **BFS**: Unweighted graphs; O(n+m); returns shortest path in hops
- **Dijkstra**: Non-negative weights; O((n+m) log n) with binary heap; greedy expansion from source
- **Bellman-Ford**: Handles negative weights; O(n*m); detects negative cycles; used in currency arbitrage detection
- **A-star**: Dijkstra + heuristic; `f(n) = g(n) + h(n)`; h must be admissible (never overestimates); optimal for pathfinding

### All-Pairs Shortest Path
- **Floyd-Warshall**: O(n^3); dynamic programming on all pairs; works with negative weights (no negative cycles)
- **Johnson's algorithm**: Reweight edges to remove negatives, then run Dijkstra from each node; O(n^2 log n + nm)
- **Application**: Financial network analysis — shortest path between two entities reveals relationship chains

### Arbitrage Detection
- **Negative cycle**: In currency graph with edge weight `= -log(exchange_rate)`, negative cycle = arbitrage opportunity
- **Detection**: Run Bellman-Ford; if any edge relaxes in round n, negative cycle exists
- **Practical**: Transaction costs, latency, and liquidity usually eliminate theoretical arbitrage

## Network Flow

### Max-Flow / Min-Cut
- **Max-flow min-cut theorem**: Maximum flow from source to sink equals minimum capacity of edges whose removal disconnects source from sink
- **Ford-Fulkerson**: Repeatedly find augmenting paths; O(m * max_flow) with DFS; can be slow for large capacities
- **Edmonds-Karp**: BFS for augmenting paths; O(n * m^2); polynomial guarantee
- **Push-relabel**: O(n^2 * m); fastest in practice for dense graphs; Goldberg's algorithm
- **Applications**: Network capacity planning, bipartite matching, image segmentation, supply chain optimization

### Min-Cost Flow
- **Problem**: Send required flow at minimum total cost; generalizes shortest path and max-flow
- **Successive shortest path**: Find cheapest augmenting path repeatedly; O(n * m * U) where U = max capacity
- **Applications**: Transportation problems, assignment problems, optimal resource allocation

## Community Detection

- **Modularity**: `Q = (1/2m) SUM((A_ij - k_i*k_j/2m) * delta(c_i, c_j))`; higher Q = better community structure
- **Louvain**: Fast greedy modularity optimization; O(n log n); widely used default algorithm
- **Leiden**: Improved Louvain with guaranteed connected communities; preferred for publication-quality results
- **Spectral**: Eigendecomposition of graph Laplacian; k communities from k smallest non-zero eigenvectors
- **Label propagation**: Each node adopts most common neighbor label; O(m); fast but non-deterministic
- **Stochastic Block Model**: Generative model; Bayesian inference of community structure; principled but slower

## PageRank and Centrality

### PageRank
- **Formula**: `PR(v) = (1-d)/n + d * SUM(PR(u) / out_degree(u))` for each in-neighbor u; damping d = 0.85
- **Interpretation**: Probability of arriving at node v via random walk with random restarts
- **Computation**: Power iteration until convergence (typically 50-100 iterations); O(m) per iteration
- **Personalized PageRank**: Bias random restart toward specific seed nodes; local influence measurement
- **Applications**: Web search ranking, paper importance, influence in social networks, stock importance in correlation networks

### Other Centrality Measures
- **Betweenness**: Fraction of shortest paths through node; identifies bridges and brokers; O(nm)
- **Closeness**: Inverse average distance to all other nodes; identifies globally accessible nodes
- **Eigenvector**: Recursive importance (connected to important = important); PageRank is a variant
- **Katz centrality**: `C_katz = (I - alpha*A)^{-1} * ones`; counts all paths, weighted by length; alpha < 1/lambda_max

## Graph Algorithms for Finance

- **Correlation networks**: Threshold stock correlations to build graph; communities = latent sectors
- **Minimum spanning tree**: MST of correlation-distance matrix reveals hierarchical stock clustering
- **Contagion modeling**: Simulate default propagation through bank lending network; identify systemic risk nodes
- **Knowledge graphs**: Entity-relationship graphs for fundamental analysis; connect companies, people, events
- **Transaction networks**: Detect money laundering patterns via subgraph matching and anomalous flow patterns

## Computational Complexity

| Problem | Algorithm | Time Complexity | Practical Limit |
|---------|-----------|----------------|-----------------|
| Shortest path (unweighted) | BFS | O(n+m) | Billions of nodes |
| Shortest path (weighted) | Dijkstra | O((n+m) log n) | Millions of nodes |
| Max flow | Push-relabel | O(n^2 * m) | Hundreds of thousands |
| Community detection | Louvain | O(n log n) | Millions of nodes |
| PageRank | Power iteration | O(m) per iter | Billions of nodes |
| All-pairs shortest path | Floyd-Warshall | O(n^3) | ~10,000 nodes |

## Risk Management

- **Scale awareness**: Choose algorithm by graph size; exact methods fail on large graphs; approximate when necessary
- **Dynamic graphs**: Static algorithms on evolving graphs produce stale results; use incremental or streaming algorithms
- **Weight interpretation**: Ensure edge weights have correct semantics (distance vs similarity vs capacity); inversions cause errors
- **Disconnected components**: Many algorithms assume connected graph; handle components separately
- **Floating point**: Shortest path algorithms with floating-point weights can have precision issues; use integer arithmetic when possible
