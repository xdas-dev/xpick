import { GestureTool, GestureToolView } from "models/tools/gestures/gesture_tool";
import { ColumnDataSource } from "models/sources/column_data_source";
import { RadioButtonGroup } from "models/widgets/radio_button_group";
import { PanEvent } from "core/ui_events";
import * as p from "core/properties";

export class PickerToolView extends GestureToolView {
  declare model: PickerTool;

  _pan_start(_e: PanEvent): void {
    console.dir(this.plot_view)
  }

  _pan(e: PanEvent): void {
    const { frame } = this.plot_view;
    const { sx, sy } = e;

    if (!frame.bbox.contains(sx, sy)) {
      return;
    }

    const x = frame.x_scale.invert(sx);
    const y = frame.y_scale.invert(sy);

    const { source } = this.model;
    source.get_array("distance").push(x);
    source.get_array("time").push(y);
    source.get_array("phase").push(this.model.phase.labels[this.model.phase.active as number]);
    source.get_array("status").push("active");
    source.change.emit();
  }

  _pan_end(_e: PanEvent): void {
    const { source } = this.model;
    var distance = source.get_array("distance") as number[];
    var time = source.get_array("time") as number[];
    var phase = source.get_array("phase") as string[];
    var status = source.get_array("status") as string[];
    var xmin = Number.POSITIVE_INFINITY;
    var xmax = Number.NEGATIVE_INFINITY;
    for (var i = 0; i < status.length; i++) {
      if (status[i] === "active") {
        if (distance[i] < xmin) {
          xmin = distance[i];
        }
        if (distance[i] > xmax) {
          xmax = distance[i];
        }
      }
    }
    var data = {
      distance: [] as number[],
      time: [] as number[],
      phase: [] as string[],
      status: [] as string[],
    };
    for (var i = 0; i < status.length; i++) {
      if (!(
        xmin <= distance[i] &&
        distance[i] <= xmax &&
        phase[i] === this.model.phase.labels[this.model.phase.active as number] &&
        status[i] === "inactive"
      )) {
        data.distance.push(distance[i]);
        data.time.push(time[i]);
        data.phase.push(phase[i]);
        data.status.push("inactive");
      }
    }
    source.data = data;
    source.change.emit();
  }
}

export namespace PickerTool {
  export type Attrs = p.AttrsOf<Props>;

  export type Props = GestureTool.Props & {
    source: p.Property<ColumnDataSource>;
    phase: p.Property<RadioButtonGroup>;
  };
}

export interface PickerTool extends PickerTool.Attrs { }

export class PickerTool extends GestureTool {
  declare properties: PickerTool.Props;
  declare __view_type__: PickerToolView;

  constructor(attrs?: Partial<PickerTool.Attrs>) {
    super(attrs);
  }

  static {
    this.prototype.default_view = PickerToolView;

    this.define<PickerTool.Props>(({ Ref }) => ({
      source: [Ref(ColumnDataSource)],
      phase: [Ref(RadioButtonGroup)],
    }));
  }

  tool_name = "Picker Tool";
  tool_icon = "bk-tool-icon-crosshair";
  event_type = "pan" as "pan";
  default_order = 12;
}
