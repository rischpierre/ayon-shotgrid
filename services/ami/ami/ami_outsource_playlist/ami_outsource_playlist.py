import rvx_beryl.farm
from ami import ami_base
from ami.ami_parameters import StringParameter

OUTSOURCE_SG_TYPE = "Outsource"
DEPARTMENT = "outsource"
HOWLER_SCRIPT = "/pipeline/AstralProjection/scripts/rvx-howler"

class AMIOutsourcePlaylist(ami_base.AmiBase):
    """Submit an outsource collection job to the farm from a selected Playlist.

    The job runs `rvx-howler collect outsource`
    on the farm via rvx_beryl. Validates that only outsource playlists are used,
    pre-populates vendor/description from the playlist, and writes back any vendor
    change the user makes.
    """

    def __init__(self, sg_session, data):
        super().__init__(sg_session, data)

        playlist_id = self.selected_ids[0]
        playlist = sg_session.find_one(
            "Playlist",
            [["id", "is", playlist_id]],
            ["code", "sg_type", "sg_vendor", "description", "sg_ayon_id"]
        )

        if not playlist:
            raise Exception(f"Playlist {playlist_id} not found")

        if playlist.get("sg_type") != OUTSOURCE_SG_TYPE:
            sg_type = playlist.get("sg_type")
            raise Exception(
                f"Playlist '{playlist['code']}' is of type '{sg_type}', "
                f"expected '{OUTSOURCE_SG_TYPE}'"
            )

        self._playlist = playlist
        self._original_vendor = playlist.get("sg_vendor") or ""
        if self._original_vendor:
            self._original_vendor = sg_session.find_one("Group", [['id', "is", self._original_vendor["id"]]], ["code"])

        self._original_vendor_name = self._original_vendor.get("code") if self._original_vendor else ""
        self._original_description = playlist.get("description") or ""

        self.vendor_param = StringParameter("Vendor", default=self._original_vendor_name)
        self.description_param = StringParameter(
            "Description", default=self._original_description
        )

    def parameters(self):
        return [self.vendor_param, self.description_param]

    def get_request_page_template(self):
        return "ami_outsource_playlist/request_page.html"

    def main(self) -> int:
        playlist_id = self.selected_ids[0]

        # Resolve project name (== AYON project name)
        project = self.sg_session.find_one(
            "Project", [["id", "is", self.project_id]], ["name"]
        )
        project_name = project["name"]

        ayon_playlist_id = self._playlist.get("sg_ayon_id")
        if not ayon_playlist_id:
            raise Exception("Playlist has no sg_ayon_id – not synced to AYON yet")

        # Write back vendor and/or description if user changed them
        new_vendor_name = self.vendor_param.value()
        new_description = self.description_param.value()

        update_data = {}
        if new_vendor_name != self._original_vendor_name:
            # Validate vendor exists
            new_vendor = self._get_vendor_from_name(new_vendor_name)
            if not new_vendor:
                raise Exception(f"Vendor '{new_vendor_name}' is not a valid vendor")
            update_data["sg_vendor"] = new_vendor

        if new_description != self._original_description:
            update_data["description"] = new_description

        if update_data:
            self.sg_session.update("Playlist", playlist_id, update_data)

        # Build farm command with vendor and description flags
        description = self.description_param.value()
        vendor = self.vendor_param.value()

        command = (
            f"{HOWLER_SCRIPT} collect outsource "
            f"--project {project_name} --playlist-id {ayon_playlist_id} "
            f"--vendor '{vendor}' --description '{description}'"
        )

        job_name = f"Howler: collect {description} [{vendor}]"

        layer = rvx_beryl.farm.CommandLineLayer(
            job_name,
            self._get_user(),
            command,
            shell_execute=True,
            department=DEPARTMENT,
        )

        rvx_beryl.farm.Job(job_name, [layer]).submit()
        return 0

    def _get_user(self) -> str:
        user_id = self.data.get("user_id")
        if user_id:
            sg_user = self.sg_session.find_one(
                "HumanUser", [["id", "is", int(user_id)]], ["login"]
            )
            if sg_user:
                return sg_user["login"].split("@")[0]
        return "unknown"

    def _get_vendor_from_name(self, name: str):
        return self.sg_session.find_one("Group", [["code", "is", name]], ["code"])
