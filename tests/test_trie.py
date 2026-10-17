import random
from collections import Counter

from core.trie import CompactTrie


def assert_invariant(trie: CompactTrie) -> None:
    total = 0
    stack = [(trie._root, True)]
    while stack:
        node, is_root = stack.pop()
        if not is_root:
            assert node.label, "aresta sem rótulo"
            assert node.bucket or len(node.children) >= 2, f"nó {node.label!r} deveria ter sido fundido"
        assert node.bucket is None or node.bucket, "bucket vazio deveria ser None"
        for first, child in node.children.items():
            assert child.label[0] == first
            stack.append((child, False))
        total += len(node.bucket or ())
    assert total == len(trie)


def test_empty():
    trie = CompactTrie()
    assert len(trie) == 0
    assert trie.search_prefix("") == []
    assert trie.search_prefix("abc") == []
    assert not trie.remove("abc", 1)


def test_insert_splits_edges():
    trie = CompactTrie()
    trie.insert("7h2y8j17", "a")
    trie.insert("7h2y8j1k", "b")
    trie.insert("7h2x0000", "c")
    trie.insert("7h2y", "d")
    assert_invariant(trie)
    assert sorted(trie.search_prefix("7h2y")) == ["a", "b", "d"]
    assert sorted(trie.search_prefix("7h2y8j1")) == ["a", "b"]
    assert sorted(trie.search_prefix("7h")) == ["a", "b", "c", "d"]
    assert trie.search_prefix("7h2z") == []


def test_prefix_ending_mid_edge():
    trie = CompactTrie()
    trie.insert("6gycfqkd", 1)
    trie.insert("7h2y8j17", 2)
    # a raiz tem duas arestas longas; "7h2" termina no meio da segunda
    assert trie.search_prefix("7h2") == [2]
    assert trie.search_prefix("7h3") == []
    assert trie.search_prefix("7h2y8j17") == [2]
    assert trie.search_prefix("7h2y8j17x") == []


def test_bucket_with_duplicates():
    trie = CompactTrie()
    for courier in ("E1", "E2", "E3"):
        trie.insert("7h2y8j17", courier)
    assert len(trie) == 3
    assert trie.search_prefix("7h2y8j17") == ["E1", "E2", "E3"]
    assert trie.remove("7h2y8j17", "E2")
    assert trie.search_prefix("7h2y") == ["E1", "E3"]
    assert_invariant(trie)


def test_remove_missing():
    trie = CompactTrie()
    trie.insert("7h2y8j17", "E1")
    assert not trie.remove("7h2y8j17", "E9")
    assert not trie.remove("7h2y8j1", "E1")
    assert not trie.remove("7h2y8j18", "E1")
    assert len(trie) == 1


def test_remove_merges_nodes():
    trie = CompactTrie()
    trie.insert("7h2y8j17", "a")
    trie.insert("7h2y8j1k", "b")
    trie.insert("7h2x0000", "c")
    trie.remove("7h2y8j1k", "b")
    assert_invariant(trie)
    trie.remove("7h2x0000", "c")
    assert_invariant(trie)
    # sobra uma única aresta com a chave inteira
    (child,) = trie._root.children.values()
    assert child.label == "7h2y8j17"
    assert trie.remove("7h2y8j17", "a")
    assert len(trie) == 0
    assert trie._root.children == {}


def test_random_operations_keep_invariant():
    # alfabeto reduzido força muitos prefixos comuns, divisões e fusões
    rng = random.Random(3)
    alphabet = "01bc"
    trie = CompactTrie()
    reference = Counter()
    keys = ["".join(rng.choice(alphabet) for _ in range(8)) for _ in range(400)]
    for step in range(10_000):
        key = rng.choice(keys)
        value = rng.randint(0, 3)
        if rng.random() < 0.55:
            trie.insert(key, value)
            reference[(key, value)] += 1
        else:
            removed = trie.remove(key, value)
            assert removed == (reference[(key, value)] > 0)
            if removed:
                reference[(key, value)] -= 1
        if step % 500 == 0:
            assert_invariant(trie)
    assert_invariant(trie)
    assert len(trie) == sum(reference.values())
    for prefix in {k[:p] for k in keys for p in range(0, 9)}:
        expected = Counter()
        for (k, v), n in reference.items():
            if k.startswith(prefix):
                expected[v] += n
        # o + unário descarta as contagens zeradas
        assert Counter(trie.search_prefix(prefix)) == +expected, prefix


def test_search_matches_linear_scan():
    rng = random.Random(4)
    alphabet = "0123456789bcdefghjkmnpqrstuvwxyz"
    keys = ["".join(rng.choice(alphabet) for _ in range(8)) for _ in range(1000)]
    trie = CompactTrie()
    for i, key in enumerate(keys):
        trie.insert(key, i)
    prefixes = {k[:p] for k in keys for p in range(1, 9)}
    prefixes |= {"".join(rng.choice(alphabet) for _ in range(rng.randint(1, 8))) for _ in range(500)}
    for prefix in prefixes:
        expected = sorted(i for i, k in enumerate(keys) if k.startswith(prefix))
        assert sorted(trie.search_prefix(prefix)) == expected, prefix


def test_stats():
    trie = CompactTrie()
    trie.insert("7h2y8j17", "a")
    trie.insert("7h2y8j1k", "b")
    trie.insert("7h2y8j1k", "c")
    stats = trie.stats()
    assert stats == {
        "nodes": 4,
        "leaves": 2,
        "terminals": 2,
        "values": 3,
        "height": 2,
        "avg_label_len": (7 + 1 + 1) / 3,
        "max_bucket": 2,
    }
