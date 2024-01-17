from bokeh.core.properties import Instance, String
from bokeh.models import ColumnDataSource, Tool


class PickerTool(Tool):
    __implementation__ = "pickertool.ts"
    source = Instance(ColumnDataSource)
    phase = String()
