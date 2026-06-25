"""
Graph-based family relationship traversal for GenHealth AI.

Uses NetworkX directed graphs to represent family trees and compute
shared disease patterns across generations.
"""

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    _NETWORKX_AVAILABLE = True
except ImportError:
    logger.warning("networkx not installed. FamilyHealthGraph unavailable.")
    _NETWORKX_AVAILABLE = False


class FamilyHealthGraph:
    """
    Directed graph representation of a family's health data.

    Nodes represent family members (and the user) with attached health summaries.
    Edges represent parent → child relationships.

    Enables:
    - Ancestor traversal (parents, grandparents, great-grandparents)
    - Shared condition detection across the tree
    - Risk overlay JSON for frontend visualization
    - Generation-level disease aggregation
    """

    def __init__(self) -> None:
        if _NETWORKX_AVAILABLE:
            self.graph: Any = nx.DiGraph()
        else:
            self.graph = None
        self._user_id: Optional[str] = None

    def __repr__(self) -> str:
        node_count = len(self.graph.nodes) if self.graph else 0
        return f"FamilyHealthGraph(nodes={node_count}, networkx={_NETWORKX_AVAILABLE})"

    def health_check(self) -> dict:
        return {
            "networkx_available": _NETWORKX_AVAILABLE,
            "node_count": len(self.graph.nodes) if self.graph else 0,
            "edge_count": len(self.graph.edges) if self.graph else 0,
        }

    # ─── Build graph ─────────────────────────────────────────────────────────

    def build_from_data(
        self,
        user_id: str,
        user_name: str,
        family_members: List[Any],
        member_conditions: Dict[str, List[str]],
    ) -> None:
        """
        Construct the family graph from family member data.

        Nodes: user + all family members
        Edges: parent → child based on relationship type

        Args:
            user_id:          The user's ID string.
            user_name:        The user's display name.
            family_members:   List of FamilyMember ORM objects.
            member_conditions: Dict mapping member_id → list of condition strings.
        """
        if not _NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available. Skipping graph build.")
            return

        self._user_id = user_id

        # Add user as central node (generation 0)
        self.graph.add_node(
            user_id,
            name=user_name,
            relationship="self",
            generation=0,
            conditions=[],
            risk_level="unknown",
        )

        for member in family_members:
            member_id = str(member.id)
            rel = (member.relationship or "unknown").lower()
            gen = self._generation_from_relationship(rel)
            conditions = member_conditions.get(member_id, [])

            # Add member node
            self.graph.add_node(
                member_id,
                name=member.name or "Unknown",
                relationship=rel,
                generation=gen,
                conditions=conditions,
                risk_level=self._compute_node_risk(conditions),
            )

            # Add directed edge: parent → child
            if gen < 0:  # Ancestor — edge from member → user
                self.graph.add_edge(member_id, user_id, relationship_type=rel)
            elif gen > 0:  # Descendant — edge from user → member
                self.graph.add_edge(user_id, member_id, relationship_type=rel)
            else:  # Sibling — bidirectional
                self.graph.add_edge(member_id, user_id, relationship_type="sibling")
                self.graph.add_edge(user_id, member_id, relationship_type="sibling")

        logger.info(
            "FamilyHealthGraph built: %d nodes, %d edges.",
            len(self.graph.nodes), len(self.graph.edges),
        )

    def build_from_db(
        self,
        user_id: str,
        db_family_members: List[Any],
        db_entities: List[Any],
    ) -> None:
        """
        Build the graph from ORM objects (database-backed).

        Args:
            user_id:           The user's ID string.
            db_family_members: FamilyMember ORM list.
            db_entities:       ExtractedEntity ORM list for family members.
        """
        # Group entities by family_member_id
        member_conditions: Dict[str, List[str]] = {}
        for entity in db_entities:
            if entity.entity_type == "DISEASE":
                mid = str(getattr(entity, "family_member_id", ""))
                if mid:
                    member_conditions.setdefault(mid, []).append(
                        entity.entity_value.lower()
                    )

        self.build_from_data(
            user_id=user_id,
            user_name="User",
            family_members=db_family_members,
            member_conditions=member_conditions,
        )

    # ─── Graph traversal ─────────────────────────────────────────────────────

    def get_ancestors(self, user_id: str, max_depth: int = 3) -> List[Dict]:
        """
        Return all ancestor nodes up to max_depth generations.

        Args:
            user_id:   Start node (the user).
            max_depth: Maximum generations to traverse (default 3).

        Returns:
            List of ancestor node attribute dicts.
        """
        if not _NETWORKX_AVAILABLE or self.graph is None:
            return []

        if user_id not in self.graph.nodes:
            return []

        ancestors = []
        visited: Set[str] = set()
        queue = [(user_id, 0)]

        while queue:
            node_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Walk backwards (predecessors = parents in our directed graph)
            for pred in self.graph.predecessors(node_id):
                if pred not in visited and pred != user_id:
                    visited.add(pred)
                    node_data = dict(self.graph.nodes[pred])
                    node_data["id"] = pred
                    node_data["depth"] = depth + 1
                    ancestors.append(node_data)
                    queue.append((pred, depth + 1))

        return ancestors

    def get_shared_conditions(self, user_id: str) -> Dict[str, List[str]]:
        """
        Find disease conditions that appear in 2+ family members.

        Args:
            user_id: The user's node ID.

        Returns:
            Dict mapping condition → list of member names who have it.
        """
        if not _NETWORKX_AVAILABLE or self.graph is None:
            return {}

        condition_holders: Dict[str, List[str]] = {}

        for node_id, attrs in self.graph.nodes(data=True):
            if node_id == user_id:
                continue
            name = attrs.get("name", "Unknown")
            for condition in attrs.get("conditions", []):
                condition_holders.setdefault(condition, []).append(name)

        # Only return conditions appearing in ≥2 members
        return {
            cond: holders
            for cond, holders in condition_holders.items()
            if len(holders) >= 2
        }

    def get_descendants(self, user_id: str, max_depth: int = 2) -> List[Dict]:
        """
        Return descendant nodes (children, grandchildren).

        Args:
            user_id:   Start node.
            max_depth: Maximum generations to descend.

        Returns:
            List of descendant node attribute dicts.
        """
        if not _NETWORKX_AVAILABLE or self.graph is None:
            return []

        descendants = []
        visited: Set[str] = set()
        queue = [(user_id, 0)]

        while queue:
            node_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for succ in self.graph.successors(node_id):
                if succ not in visited and succ != user_id:
                    visited.add(succ)
                    node_data = dict(self.graph.nodes[succ])
                    node_data["id"] = succ
                    node_data["depth"] = depth + 1
                    descendants.append(node_data)
                    queue.append((succ, depth + 1))

        return descendants

    # ─── Visualization ────────────────────────────────────────────────────────

    def visualize_risk_overlay(self, user_id: str) -> Dict:
        """
        Return a JSON-serializable representation of the family tree
        with risk data for frontend D3.js / force-graph visualization.

        Node schema:
            {id, name, relationship, generation, conditions[], risk_level}
        Edge schema:
            {source, target, relationship_type}

        Args:
            user_id: The user's node ID.

        Returns:
            {nodes: [...], edges: [...]}
        """
        if not _NETWORKX_AVAILABLE or self.graph is None:
            return {"nodes": [], "edges": []}

        nodes = []
        for node_id, attrs in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": attrs.get("name", "Unknown"),
                "relationship": attrs.get("relationship", "unknown"),
                "generation": attrs.get("generation", 0),
                "conditions": attrs.get("conditions", []),
                "risk_level": attrs.get("risk_level", "unknown"),
                "is_user": node_id == user_id,
            })

        edges = []
        for source, target, edge_attrs in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "relationship_type": edge_attrs.get("relationship_type", "unknown"),
            })

        return {"nodes": nodes, "edges": edges}

    def disease_prevalence_by_generation(self) -> Dict[int, Dict[str, int]]:
        """
        Count disease occurrences per generation.

        Returns:
            Dict mapping generation_number → {disease: count}
        """
        if not _NETWORKX_AVAILABLE or self.graph is None:
            return {}

        gen_diseases: Dict[int, Dict[str, int]] = {}
        for _, attrs in self.graph.nodes(data=True):
            gen = attrs.get("generation", 0)
            for condition in attrs.get("conditions", []):
                gen_diseases.setdefault(gen, {})
                gen_diseases[gen][condition] = gen_diseases[gen].get(condition, 0) + 1

        return gen_diseases

    # ─── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _generation_from_relationship(rel: str) -> int:
        """Map a relationship string to a generation number."""
        rel = rel.lower()
        if "great" in rel and "grand" in rel:
            return -3
        if "grand" in rel and any(kw in rel for kw in ("father", "mother", "parent")):
            return -2
        if any(kw in rel for kw in ("father", "mother", "parent")):
            return -1
        if any(kw in rel for kw in ("son", "daughter", "child")):
            return 1
        if any(kw in rel for kw in ("grandson", "granddaughter", "grandchild")):
            return 2
        if any(kw in rel for kw in ("uncle", "aunt")):
            return -1
        return 0  # Sibling, spouse, cousin

    @staticmethod
    def _compute_node_risk(conditions: List[str]) -> str:
        """Derive a simple risk level from a member's conditions list."""
        high_risk_conditions = {
            "coronary", "heart", "stroke", "cancer", "diabetes", "hypertension"
        }
        moderate_risk = {"thyroid", "asthma", "depression", "arthritis", "kidney"}

        for cond in conditions:
            if any(kw in cond for kw in high_risk_conditions):
                return "high"
        for cond in conditions:
            if any(kw in cond for kw in moderate_risk):
                return "moderate"
        return "low" if conditions else "unknown"
