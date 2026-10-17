"""Trie compacta (árvore radix) para chaves string.

Cada aresta é rotulada por uma substring, guardada no nó filho. Todo nó que não é a raiz
tem bucket não vazio ou pelo menos dois filhos; por isso uma subárvore com k valores tem
O(k) nós, e a busca por prefixo custa O(m + k).
"""


class _Node:
    __slots__ = ("label", "children", "bucket")

    def __init__(self, label: str = "", bucket: list | None = None) -> None:
        self.label = label
        # chave: primeiro caractere do rótulo do filho
        self.children: dict[str, _Node] = {}
        # None quando o nó não é terminal
        self.bucket = bucket


def _common_prefix_length(label: str, key: str, start: int) -> int:
    n = min(len(label), len(key) - start)
    i = 0
    while i < n and label[i] == key[start + i]:
        i += 1
    return i


class CompactTrie:
    __slots__ = ("_root", "_size")

    def __init__(self) -> None:
        self._root = _Node()
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def insert(self, key: str, value) -> None:
        """Insere `value` sob `key`. Chaves repetidas acumulam valores no mesmo bucket. O(|key|)."""
        node, i = self._root, 0
        while True:
            if i == len(key):
                if node.bucket is None:
                    node.bucket = []
                node.bucket.append(value)
                break

            child = node.children.get(key[i])
            if child is None:
                node.children[key[i]] = _Node(key[i:], [value])
                break

            common = _common_prefix_length(child.label, key, i)
            if common == len(child.label):
                node, i = child, i + common
                continue

            # A chave diverge no meio da aresta: cria um nó intermediário
            middle = _Node(child.label[:common])
            child.label = child.label[common:]
            middle.children[child.label[0]] = child
            node.children[key[i]] = middle
            i += common
            if i == len(key):
                middle.bucket = [value]
            else:
                middle.children[key[i]] = _Node(key[i:], [value])
            break
        self._size += 1

    def remove(self, key: str, value) -> bool:
        """Remove uma ocorrência de `value` sob `key`. Devolve False se não existir. O(|key| + b)."""
        parent, node, i = None, self._root, 0
        while i < len(key):
            child = node.children.get(key[i])
            if child is None or not key.startswith(child.label, i):
                return False
            parent, node, i = node, child, i + len(child.label)

        if node.bucket is None or value not in node.bucket:
            return False
        node.bucket.remove(value)
        if not node.bucket:
            node.bucket = None
        self._size -= 1

        if node is self._root:
            return True
        if node.bucket is None and not node.children:
            del parent.children[node.label[0]]
            node = parent
        if node is not self._root and node.bucket is None and len(node.children) == 1:
            self._merge_with_child(node)
        return True

    @staticmethod
    def _merge_with_child(node: _Node) -> None:
        (child,) = node.children.values()
        node.label += child.label
        node.children = child.children
        node.bucket = child.bucket

    def search_prefix(self, prefix: str) -> list:
        """Todos os valores cujas chaves começam com `prefix`. O(m + k)."""
        node, i, m = self._root, 0, len(prefix)
        while i < m:
            child = node.children.get(prefix[i])
            if child is None:
                return []
            label = child.label
            if m - i < len(label):
                # o prefixo termina no meio desta aresta
                return self._collect(child) if label.startswith(prefix[i:]) else []
            if not prefix.startswith(label, i):
                return []
            node, i = child, i + len(label)
        return self._collect(node)

    @staticmethod
    def _collect(node: _Node) -> list:
        out = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.bucket:
                out.extend(current.bucket)
            stack.extend(current.children.values())
        return out

    def stats(self) -> dict:
        """Métricas da estrutura, usadas no relatório."""
        nodes = leaves = terminals = label_chars = max_bucket = height = 0
        stack = [(self._root, 0)]
        while stack:
            node, depth = stack.pop()
            nodes += 1
            height = max(height, depth)
            label_chars += len(node.label)
            if not node.children:
                leaves += 1
            if node.bucket:
                terminals += 1
                max_bucket = max(max_bucket, len(node.bucket))
            stack.extend((child, depth + 1) for child in node.children.values())
        return {
            "nodes": nodes,
            "leaves": leaves,
            "terminals": terminals,
            "values": self._size,
            "height": height,
            "avg_label_len": label_chars / (nodes - 1) if nodes > 1 else 0.0,
            "max_bucket": max_bucket,
        }
