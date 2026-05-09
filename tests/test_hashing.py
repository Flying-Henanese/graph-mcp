from archimedes.skeleton import calculate_structural_hash, get_structural_code


def test_structural_hash_consistency():
    code1 = "def foo():\n    print(1)"
    code2 = "def foo():\n    print(2)" # Logic changes

    sk1 = get_structural_code(code1)
    sk2 = get_structural_code(code2)

    assert sk1 == sk2
    assert calculate_structural_hash(sk1) == calculate_structural_hash(sk2)

def test_structural_hash_change():
    code1 = "def foo(): pass"
    code2 = "def bar(): pass" # Signature changes

    sk1 = get_structural_code(code1)
    sk2 = get_structural_code(code2)

    assert sk1 != sk2
    assert calculate_structural_hash(sk1) != calculate_structural_hash(sk2)
