import main
import pytest

def is_palindrome(word):
    return word == word[::-1]

# test_with_pytest.py

def test_always_passes():
    assert True

def test_uppercase():
    assert "loud noises".upper() == "LOUD NOISES"

def test_reversed():
    assert list(reversed([1, 2, 3, 4])) == [4, 3, 2, 1]

def test_some_primes():
    assert 37 in {
        num
        for num in range(1, 50)
        if num != 1 and not any([num % div == 0 for div in range(2, num)])
    }

@pytest.mark.parametrize("palindrome", [
    "",
    "a",
    "BoB",
    "AnnA",
    "GOTOTOG",
])
def test_is_palindrome(palindrome):
    assert is_palindrome(palindrome)

@pytest.fixture
def example_people_data():
    return [
        {
            "given_name": "Alfonsa",
            "family_name": "Ruiz",
            "title": "Senior Software Engineer",
        },
        {
            "given_name": "Sayid",
            "family_name": "Khan",
            "title": "Project Manager",
        },
    ]