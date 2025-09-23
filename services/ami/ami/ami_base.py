


class AmiBase:
    def __init__(self, sg_session, data):
        self.sg_session = sg_session
        self.data = data
        self.selected_ids = data.get("selected_ids")
        self.project_id = int(data.get("project_id"))

    def main(self):
        raise NotImplementedError

    def parameters(self):
        raise NotImplementedError