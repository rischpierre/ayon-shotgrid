from typing import Any, Dict, List, Optional, Union


class AmiBase:
    """Base class for AMI (Action Menu Item) handlers.

    Subclasses should implement:
      - parameters(): to declare user-adjustable parameters (optional).
      - main(): to perform the actual work; return 0 on success, non-zero otherwise.
      - get_request_page_template(): to provide custom parameters page template (optional).
      - get_request_page_template(): to provide custom result page template (optional).
    """

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        """Initialize the AMI handler.

        Args:
            sg_session: Shotgun/ShotGrid API session (or compatible object).
            data: Request payload dictionary containing action context.
        """
        self.sg_session: Any = sg_session
        self.data: Dict[str, Any] = data
        self.selected_ids: list[int] = [int(x) for x in data.get("selected_ids").split(",")]
        self.entity_type: str = data.get("entity_type")
        if self.entity_type == "Project":
            self.project_id: int = self.selected_ids[0]
        else:
            self.project_id = int(data.get("project_id"))


    def main(self):
        raise NotImplementedError

    def parameters(self) -> List[Any]:
        """Return a list of parameter objects (may be empty)."""
        raise NotImplementedError

    def get_request_page_template(self) -> Optional[str]:
        """Return path to custom parameters template or None to use default."""
        return None

    def get_result_page_template(self) -> Optional[str]:
        """Return path to custom result template or None to use default."""
        return None
