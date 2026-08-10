class ColorCache(object):
    def __init__(self):
        # Use these colors for labels
        self.colors = [
            "#FFFFFF", "#999999", "#FF9999", "#FFCC99", "#FFFF99", "#CCFF99",
            "#99FF99", "#99FFCC", "#99FFFF", "#99CCFF", "#9999FF", "#CC99FF",
            "#FF99FF", "#FF99CC",
        ]
        # Labels are cached here
        self.colorBuf = {}

    # Get a unique color for a given ID, reusing colors as we go
    def getColor(self, id) -> str:
        if id in self.colorBuf:
            # Sort entries in order of freshness
            color = self.colorBuf.pop(id)
        elif len(self.colorBuf) < len(self.colors):
            # Assign each initial entry color based on its order
            color = self.colors[len(self.colorBuf)]
        else:
            # If we run out of colors, reuse the oldest entry
            color = self.colorBuf.pop(next(iter(self.colorBuf)))
        # Done
        self.colorBuf[id] = color
        return color

    def rename(self, old_id: str, new_id: str):
        if old_id in self.colorBuf and new_id != old_id:
            self.colorBuf[new_id] = self.colorBuf[old_id]
            del self.colorBuf[old_id]
