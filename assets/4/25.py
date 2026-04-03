def floyd_warshall(graph):
    n = len(graph)
    
    dist = [[float('inf')] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            dist[i][j] = graph[i][j]
    
    next_node = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and graph[i][j] != float('inf'):
                next_node[i][j] = j
    
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
                    next_node[i][j] = next_node[i][k]
    
    return dist, next_node


def reconstruct_path(start, end, next_node):
    if next_node[start][end] is None:
        return None
    
    path = [start]
    while start != end:
        start = next_node[start][end]
        path.append(start)
    
    return path