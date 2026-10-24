"""Question positions and navigation controls, separate from saved answer values."""

from collections.abc import Sequence

BACK_ACTION = "__previous_question__"
NEXT_ACTION = "__next_question__"
PAUSE_ACTION = "__pause_session__"
RESTART_ACTION = "__restart_session__"

# Session controls in the order they appear in the terminal key bar.
CONTROL_ACTIONS = (BACK_ACTION, NEXT_ACTION, PAUSE_ACTION, RESTART_ACTION)


class QuestionMoved(Exception):
    """Unwind the current prompt so the questionnaire can visit another question."""

    def __init__(self, direction: int) -> None:
        self.direction = direction


class QuestionNavigation:
    """Track a position across sections without deleting or rewriting saved answers."""

    def __init__(self, questions: Sequence[tuple[str, bool]]) -> None:
        self.keys = [key for key, _ in questions]
        self.shown_sections: set[str] = set()
        self.moving = False
        self.position = next(
            (index for index, (_, answered) in enumerate(questions) if not answered),
            len(questions),
        )

    def includes(self, key: str) -> bool:
        """Whether this is the question currently being visited."""
        return self.position < len(self.keys) and self.keys[self.position] == key

    def advance(self) -> None:
        """Move forward after an explicitly submitted answer."""
        self.position += 1
        self.moving = False

    def move(self, direction: int) -> None:
        """Move within the questionnaire, including its completion screen."""
        self.moving = True
        self.position = min(len(self.keys), max(0, self.position + direction))


def pending(navigation: QuestionNavigation | None, key: str, answered: bool) -> bool:
    """Keep ordinary resume behavior for callers without navigation."""
    return navigation.includes(key) if navigation is not None else not answered


def configure_prompt(
    prompter: object, navigation: QuestionNavigation | None, default: str | list[str] | None
) -> None:
    """Expose navigation and the saved answer through an optional terminal hook."""
    configure = getattr(prompter, "question_navigation", None)
    if callable(configure):
        configure(navigation, default)
