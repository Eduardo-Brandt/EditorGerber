"""Worker-local reuse; completed snapshots never mutate earlier PCB results."""


class GeometryMemo:
    def __init__(self, previous=None):
        self.previous = previous or {}
        self.current = {}

    def get(self, key, token, sources, compute):
        record = self.current.get(key, self.previous.get(key))
        if (
            record is not None
            and record[0] == token
            and len(record[1]) == len(sources)
            and all(old is new for old, new in zip(record[1], sources, strict=True))
        ):
            value = record[2]
        else:
            value = compute()
        # Keep source geometries alive: reuse is based on identity, never on
        # recycled Python IDs or expensive polygon equality comparisons.
        self.current[key] = token, sources, value
        return value
