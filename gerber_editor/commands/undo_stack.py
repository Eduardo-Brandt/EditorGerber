"""UI-independent command history with bounded retention."""

from typing import Callable, Protocol


class Command(Protocol):
    label: str

    def redo(self) -> None: ...

    def undo(self) -> None: ...


class UndoStack:
    def __init__(self, on_change: Callable[[], None] | None = None, limit: int = 500):
        self._commands: list[Command] = []
        self._index = 0
        self.limit = limit
        self.on_change = on_change or (lambda: None)

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._commands)

    def push(self, command: Command) -> None:
        command.redo()
        del self._commands[self._index :]
        self._commands.append(command)
        if len(self._commands) > self.limit:
            self._commands.pop(0)
        self._index = len(self._commands)
        self.on_change()

    def undo(self) -> None:
        if self.can_undo:
            self._index -= 1
            self._commands[self._index].undo()
            self.on_change()

    def redo(self) -> None:
        if self.can_redo:
            self._commands[self._index].redo()
            self._index += 1
            self.on_change()
