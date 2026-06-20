bl_info = {
    "name": "Send to B-Renderon",
    "author": "Aeternus + Grok",
    "version": (1, 2, 1),
    "blender": (5, 0, 0),
    "location": "Properties > Output > Send to B-Renderon",
    "description": "Send jobs to B-Renderon (marker + view layer support)",
    "category": "Render",
}

import bpy
import json
import os
from pathlib import Path

QUEUE_NAME = "Default"

def get_blend_prefix(blend_path):
    stem = os.path.splitext(os.path.basename(blend_path))[0].upper()
    for p in ("PNT", "TXT", "VID"):
        if stem.startswith(p):
            return p
    return None

def detect_phase(blend_path):
    lower = blend_path.lower()
    for p in ("phase 3", "phase 2", "phase 1"):
        if p in lower:
            return p.title()
    return "Phase 1"

def get_camera_ranges(scene):
    markers = [m for m in scene.timeline_markers if m.camera]
    markers.sort(key=lambda m: m.frame)
    ranges = []
    for i, m in enumerate(markers):
        start = m.frame
        end = markers[i+1].frame - 1 if i + 1 < len(markers) else scene.frame_end
        ranges.append({"camera": m.camera.name, "start": start, "end": end})
    return ranges

class SEND_TO_BRENDERON_OT_send(bpy.types.Operator):
    bl_idname = "send_to_brenderon.send"
    bl_label = "Send Jobs to B-Renderon"
    bl_description = "Send current jobs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Please save the .blend file first!")
            return {'CANCELLED'}

        prefix = get_blend_prefix(blend_path)
        if not prefix:
            self.report({'ERROR'}, "Filename must start with PNT, TXT or VID")
            return {'CANCELLED'}

        jobs = []
        view_layers = [vl.name for vl in scene.view_layers if vl.use]

        ranges = get_camera_ranges(scene) if prefix in ("PNT", "TXT") else []

        if ranges:
            for r in ranges:
                for vl_name in view_layers:
                    jobs.append({
                        "ruta_blend": blend_path,
                        "nombre_blend": os.path.basename(blend_path),
                        "escena": scene.name,
                        "view_layer": vl_name,
                        "camara": r["camera"],
                        "inicio": str(r["start"]),
                        "fin": str(r["end"]),
                        "modo": "Animation",
                        "estado": "no_comenzado",
                    })
        else:
            for vl_name in view_layers:
                jobs.append({
                    "ruta_blend": blend_path,
                    "nombre_blend": os.path.basename(blend_path),
                    "escena": scene.name,
                    "view_layer": vl_name,
                    "camara": scene.camera.name if scene.camera else "",
                    "inicio": str(scene.frame_start),
                    "fin": str(scene.frame_end),
                    "modo": "Animation",
                    "estado": "no_comenzado",
                })

        if not jobs:
            self.report({'ERROR'}, "No jobs generated")
            return {'CANCELLED'}

        # Write to queue as JSON Lines
        queue_file = Path(r"D:\B-Renderon\queues") / f"{QUEUE_NAME}.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            lines = []
            if queue_file.exists():
                with open(queue_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

            for job in jobs:
                lines.append(json.dumps(job, ensure_ascii=False) + "\n")

            with open(queue_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            self.report({'INFO'}, f"✅ Successfully sent {len(jobs)} job(s) to B-Renderon queue!")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to write queue: {e}")
            return {'CANCELLED'}


class SEND_TO_BRENDERON_PT_panel(bpy.types.Panel):
    bl_label = "Send to B-Renderon"
    bl_idname = "SEND_TO_BRENDERON_PT_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"

    def draw(self, context):
        layout = self.layout
        blend_path = bpy.data.filepath

        if not blend_path:
            layout.label(text="Save .blend file first", icon='ERROR')
            return

        prefix = get_blend_prefix(blend_path) or "Unknown"
        layout.label(text=f"Type: {prefix}", icon='FILE_BLEND')
        layout.label(text=f"Phase: {detect_phase(blend_path)}", icon='RENDERLAYERS')

        layout.separator()
        layout.operator("send_to_brenderon.send", icon='RENDER_ANIMATION', text="Send Jobs")


def register():
    bpy.utils.register_class(SEND_TO_BRENDERON_OT_send)
    bpy.utils.register_class(SEND_TO_BRENDERON_PT_panel)

def unregister():
    bpy.utils.unregister_class(SEND_TO_BRENDERON_OT_send)
    bpy.utils.unregister_class(SEND_TO_BRENDERON_PT_panel)

if __name__ == "__main__":
    register()