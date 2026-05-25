"""
Dijkstra算法 - 分步执行版本
支持逐步展示算法执行过程，用于教学可视化
"""
import heapq
import time
from typing import Dict, List, Tuple, Optional, Generator
from collections import defaultdict


class DijkstraStepState:
    """Dijkstra算法单个步骤的状态快照"""

    def __init__(self):
        self.step_number: int = 0
        self.current_node: Optional[int] = None
        self.distances: Dict[int, int] = {}
        self.visited: set = set()
        self.frontier: set = set()
        self.relaxed_edges: List[Tuple[int, int, int]] = []
        self.paths: Dict[int, List[int]] = {}
        self.description: str = ""
        self.phase: str = ""  # "init", "select", "relax", "complete"
        self.is_complete: bool = False


class SteppedDijkstra:
    """支持分步执行的Dijkstra算法"""

    def __init__(self):
        self.states: List[DijkstraStepState] = []
        self.final_result: Dict[int, Tuple[int, List[int]]] = {}
        self.total_steps: int = 0

    def calculate_with_steps(
        self,
        source: int,
        graph: Dict[int, List[Tuple[int, int]]],
    ) -> List[DijkstraStepState]:
        """
        执行Dijkstra算法并记录每一步的中间状态

        Returns:
            List[DijkstraStepState] - 每一步的状态快照列表
        """
        self.states = []
        self.final_result = {}

        distances = {source: 0}
        paths = {source: [source]}
        visited = set()
        pq = [(0, source, 0)]
        step_counter = 0

        # 步骤0: 初始状态
        init_state = DijkstraStepState()
        init_state.step_number = 0
        init_state.distances = {source: 0}
        init_state.visited = set()
        init_state.frontier = set()
        init_state.paths = {source: [source]}
        init_state.description = f"初始状态：从源节点 {source} 开始。距离设为0，其他节点距离为无穷大。"
        init_state.phase = "init"
        self.states.append(init_state)
        step_counter = 1

        while pq:
            curr_cost, curr_node, _ = heapq.heappop(pq)

            if curr_node in visited:
                continue
            if curr_cost > distances.get(curr_node, float('inf')):
                continue

            # 步骤: 选择当前节点
            visited.add(curr_node)
            frontier = set()
            for _, (c, n, _) in enumerate(pq):
                if n not in visited:
                    frontier.add(n)

            select_state = DijkstraStepState()
            select_state.step_number = step_counter
            select_state.current_node = curr_node
            select_state.distances = dict(distances)
            select_state.visited = set(visited)
            select_state.frontier = set(frontier)
            select_state.paths = {k: list(v) for k, v in paths.items()}
            select_state.description = (
                f"选择节点 {curr_node}（当前距离={curr_cost}）作为下一个永久标记节点。"
                f"将其加入已访问集合。"
            )
            select_state.phase = "select"
            self.states.append(select_state)
            step_counter += 1

            # 松弛邻接节点
            relaxed_edges = []
            if curr_node in graph:
                for neighbor, edge_cost in graph[curr_node]:
                    new_cost = curr_cost + edge_cost
                    old_cost = distances.get(neighbor, float('inf'))

                    if new_cost < old_cost:
                        distances[neighbor] = new_cost
                        paths[neighbor] = paths[curr_node] + [neighbor]
                        heapq.heappush(pq, (new_cost, neighbor, step_counter))
                        relaxed_edges.append((curr_node, neighbor, new_cost))

            if relaxed_edges:
                # 如果有松弛操作，记录松弛步骤
                new_frontier = set()
                for _, (c, n, _) in enumerate(pq):
                    if n not in visited:
                        new_frontier.add(n)

                relax_state = DijkstraStepState()
                relax_state.step_number = step_counter
                relax_state.current_node = curr_node
                relax_state.distances = dict(distances)
                relax_state.visited = set(visited)
                relax_state.frontier = set(new_frontier)
                relax_state.paths = {k: list(v) for k, v in paths.items()}
                relax_state.relaxed_edges = list(relaxed_edges)
                node_labels = ", ".join(
                    f"{n}(距离→{d})" for _, n, d in relaxed_edges
                )
                relax_state.description = (
                    f"从节点 {curr_node} 松弛邻接边：{node_labels}。"
                    f"更新这些节点的最短距离和路径。"
                )
                relax_state.phase = "relax"
                self.states.append(relax_state)
                step_counter += 1

        # 最终完成状态
        final_state = DijkstraStepState()
        final_state.step_number = step_counter
        final_state.distances = dict(distances)
        final_state.visited = set(visited)
        final_state.paths = {k: list(v) for k, v in paths.items()}
        final_state.description = "算法完成！所有可达节点的最短路径已找到。"
        final_state.phase = "complete"
        final_state.is_complete = True
        self.states.append(final_state)

        self.total_steps = len(self.states)

        # 构建最终结果
        for dest in distances:
            if dest != source:
                self.final_result[dest] = (distances[dest], paths.get(dest, []))

        return self.states

    def get_state(self, step: int) -> Optional[DijkstraStepState]:
        """获取指定步骤的状态"""
        if 0 <= step < len(self.states):
            return self.states[step]
        return None

    def get_total_steps(self) -> int:
        return self.total_steps
