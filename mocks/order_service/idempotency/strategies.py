from abc import ABC, abstractmethod
from enum import Enum


class Decision(str, Enum):
    PROCESS_NEW = "PROCESS_NEW"
    SKIP_AS_DUPLICATE = "SKIP_AS_DUPLICATE"
    RECOVER_PARTIAL = "RECOVER_PARTIAL"


class IdempotencyStrategy(ABC):
    @abstractmethod
    def should_process(self, key: str, attempt, current_state) -> Decision: ...