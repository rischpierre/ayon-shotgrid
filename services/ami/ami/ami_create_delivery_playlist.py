from datetime import datetime
from typing import Any, Dict, List

from services.ami.ami import ami_base
from services.ami.ami.ami_parameters import StringParameter


class AMICreateDeliveryPlaylist(ami_base.AmiBase):
    """Create a delivery playlist for selected versions.

    The default playlist name is generated as 'delivery_YYYY-MM-DD_##' where
    the numeric suffix increments to the next available version for the day.
    """

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        super().__init__(sg_session, data)
        today_str = datetime.now().strftime("%Y-%m-%d")
        base_name = f"delivery_{today_str}"
        version = self._get_next_available_version(base_name)
        name = f"{base_name}_{version:02d}"

        self.playlist_param = StringParameter("Playlist Name", default=name)

    def _get_next_available_version(self, base_name: str) -> int:
        """Find the next numeric suffix for a playlist code containing base_name."""
        playlists = self.sg_session.find(
            "Playlist",
            [["project.Project.id", "is", self.project_id], ["code", "contains", f"{base_name}"]],
            ["code"]
        )
        max_ = 0
        for p in playlists:
            digits = p["code"].split("_")[-1]
            try:
                value = int(digits)
                if value > max_:
                    max_ = value
            except ValueError:
                continue
        return max_ + 1

    def parameters(self) -> List[StringParameter]:
        """Expose the configurable parameters for this action."""
        return [self.playlist_param]

    def main(self) -> int:
        """Create a playlist containing the selected versions."""
        versions_ids = [int(x) for x in self.selected_ids.split(",")]  # type: ignore[union-attr]
        if not versions_ids:
            raise Exception("Found no selected versions")

        versions = self.sg_session.find(
            "Version",
            [["id", "in", versions_ids]],
            ["code", "sg_path_to_movie"]
        )

        data = {
            "project": {"id": self.project_id, "type": "Project"},
            "code": self.playlist_param.value(),
            "versions": versions,
        }
        result = self.sg_session.create("Playlist", data)
        if result:
            return 0
        else:
            return -1
