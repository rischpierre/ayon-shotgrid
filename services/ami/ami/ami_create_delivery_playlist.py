from datetime import datetime

from services.ami.ami import ami_base
from services.ami.ami.ami_parameters import StringParameter


class AMICreateDeliveryPlaylist(ami_base.AmiBase):
    def __init__(self, sg_session, data):
        super().__init__(sg_session, data)
        today_str = datetime.now().strftime("%Y%m%d")
        name = f"{today_str}_delivery_playlist",
        self.playlist_param = StringParameter("Playlist Name", default=name)

    def parameters(self):
        return [self.playlist_param]

    def main(self):
        versions_ids = [int(x) for x in self.selected_ids.split(",")]
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
        result  = self.sg_session.create("Playlist", data)
        if result:
            return 0
        else:
            return -1