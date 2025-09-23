from typing import Any, Dict, List, Optional, Union


class AmiBase:
    """Base class for AMI (Action Menu Item) handlers.

    Subclasses should implement:
      - parameters(): to declare user-adjustable parameters (optional).
      - main(): to perform the actual work; return 0 on success, non-zero otherwise.
    """

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        """Initialize the AMI handler.

        Args:
            sg_session: Shotgun/ShotGrid API session (or compatible object).
            data: Request payload dictionary containing action context.
        """
        self.sg_session: Any = sg_session
        self.data: Dict[str, Any] = data
        self.selected_ids: Optional[Union[str, list, dict]] = data.get("selected_ids")
        self.project_id: int = int(data.get("project_id"))

    def main(self):
        raise NotImplementedError

    def parameters(self) -> List[Any]:
        """Return a list of parameter objects (may be empty)."""
        raise NotImplementedError
