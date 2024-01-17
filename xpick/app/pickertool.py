from bokeh.core.properties import Instance
from bokeh.models import ColumnDataSource, RadioButtonGroup, Tool


class PickerTool(Tool):
    __implementation__ = "pickertool.ts"
    source = Instance(ColumnDataSource)
    phase = Instance(RadioButtonGroup)
