import itertools
from typing import Iterable
from typing import Iterator
from typing import MutableSet
from typing import TypeVar

T = TypeVar("T")


class OrderedSet(MutableSet[T]):
    """A set that preserves insertion order by internally using a dict.

    >>> OrderedSet([1, 2, "foo"])
    OrderedSet([1, 2, 'foo'])


    >>> OrderedSet([1, 2, 3, 3, 2, 1, 'a', 'b', 'a', 'c'])
    OrderedSet([1, 2, 3, 'a', 'b', 'c'])

    >>> s = OrderedSet([1, 2, 3])
    >>> s.add(4)
    >>> s
    OrderedSet([1, 2, 3, 4])

    >>> s = OrderedSet([1, 2, 3])
    >>> "foo" in s
    False

    >>> 1 in s
    True

    >>> list(s)
    [1, 2, 3]

    >>> s == OrderedSet([1, 2, 3])
    True

    >>> s > OrderedSet([1, 2])  # set is a superset of other
    True

    >>> s & {2}
    OrderedSet([2])

    >>> s | {4}
    OrderedSet([1, 2, 3, 4])

    >>> s - {2}
    OrderedSet([1, 3])

    >>> s - {1}
    OrderedSet([2, 3])

    >>> {1} - s
    OrderedSet([])

    >>> s ^ {2}
    OrderedSet([1, 3])

    >>> s[1]
    2

    >>> s[2]
    3

    >>> eval(repr(OrderedSet(['a', 'b', 'c'])))
    OrderedSet(['a', 'b', 'c'])



    """

    __slots__ = ("_d",)

    def __init__(self, iterable: "Iterable[T] | None" = None):
        self._d = dict.fromkeys(iterable) if iterable else {}

    def add(self, x: T) -> None:
        self._d[x] = None

    def clear(self) -> None:
        self._d.clear()

    def discard(self, x: T) -> None:
        self._d.pop(x, None)

    def __getitem__(self, index) -> T:
        try:
            return next(itertools.islice(self._d, index, index + 1))
        except StopIteration as e:
            raise IndexError(f"index {index} out of range") from e

    def __contains__(self, x: object) -> bool:
        return self._d.__contains__(x)

    def __len__(self) -> int:
        return self._d.__len__()

    def __iter__(self) -> Iterator[T]:
        return self._d.__iter__()

    def __str__(self):
        return f"{{{', '.join(str(i) for i in self)}}}"

    def __repr__(self):
        return f"OrderedSet({list(self._d.keys())})"
