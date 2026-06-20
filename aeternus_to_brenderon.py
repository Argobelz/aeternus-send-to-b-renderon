bl_info = {
    "name": "Send to B-Renderon",
    "author": "Aeternus + Grok",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "Properties > Output > Send to B-Renderon",
    "description": "Sends render jobs to B-Renderon queue manager",
    "category": "Render",
}

import bpy
import json
import os
import re
import subprocess
from pathlib import Path

# ========================= CONFIG =========================
B_RENDERON_PATH = r"D:\B-Renderon\B-renderon.exe"
QUEUE_NAME = "Default"
# =======================================================

def get_blend_prefix(blend_path):
    stem = os.path.splitext(os.path.basename(blend_path))[0].upper()
    for pfx in ("PNT", "TXT", "VID"):
        if stem.startswith(pfx):
            return pfx
    return None

def detect_phase(blend_path):
    lower = blend_path.lower()
    for p in ("phase 3", "phase 2", "phase 1"):
        if p in lower:
            return p.replace(" ", " ")
    return "Phase 1"

def parse_shot(name):
    m = re.match(r"(EPS(\d+))_(SQ\d+)_(SH[0-9A-Z]+)", name.strip(), re.IGNORECASE)
    if not m:
        return None
    eps_num = m.group(2)
    return {
        "eps_folder": f"EPS{eps_num.zfill(3)}",
        "sq": m.group(3).upper(),
        "sh": m.group(4).upper(),
    }

def launch_b_renderon():
    if os.path.exists(B_RENDERON_PATH):
        try:
            subprocess.Popen([B_RENDERON_PATH])
            print("B-Renderon launched.")
        except Exception as e:
            print(f"Failed to launch B-Renderon: {e}")

class SEND_TO_BRENDERON_OT_send(bpy.types.Operator):
    bl_idname = "send_to_brenderon.send"
    bl_label = "Send Jobs to B-Renderon"
    bl_description = "Send current scene jobs to B-Renderon"
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

        phase = detect_phase(blend_path)
        jobs = []

        view_layers = [vl.name for vl in scene.view_layers if vl.use]

        if prefix in ("PNT", "TXT"):
            # Simple version: one job per view layer using scene range
            for vl_name in view_layers:
                job = {
                    "blend_path": blend_path,
                    "scene": scene.name,
                    "view_layer": vl_name,
                    "frame_start": scene.frame_start,
                    "frame_end": scene.frame_end,
                    "output_path": "",
                    "mode": "Animation"
                }
                jobs.append(job)
        else:  # VID
            for vl_name in view_layers:
                job = {
                    "blend_path": blend_path,
                    "scene": scene.name,
                    "view_layer": vl_name,
                    "frame_start": scene.frame_start,
                    "frame_end": scene.frame_end,
                    "output_path": "",
                    "mode": "Animation"
                }
                jobs.append(job)

        if not jobs:
            self.report({'ERROR'}, "No view layers enabled")
            return {'CANCELLED'}

        # Write to B-Renderon queue
        queue_dir = Path(r"D:\B-Renderon\queues")
        queue_dir.mkdir(parents=True, exist_ok=True)
        queue_file = queue_dir / f"{QUEUE_NAME}.json"

        try:
            if queue_file.exists():
                with open(queue_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"jobs": []}

            data["jobs"].extend(jobs)

            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            launch_b_renderon()

            self.report({'INFO'}, f"Sent {len(jobs)} job(s) to B-Renderon!")
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
        scene = context.scene
        blend_path = bpy.data.filepath

        if not blend_path:
            layout.label(text="Save .blend file first", icon='ERROR')
            return

        prefix = get_blend_prefix(blend_path)
        layout.label(text=f"Type: {prefix or 'Unknown'}", icon='FILE_BLEND')
        layout.label(text=f"Phase: {detect_phase(blend_path)}", icon='RENDERLAYERS')

        layout.separator()
        row = layout.row()
        row.operator("send_to_brenderon.send", icon='RENDER_ANIMATION', text="Send Jobs")


def register():
    bpy.utils.register_class(SEND_TO_BRENDERON_OT_send)
    bpy.utils.register_class(SEND_TO_BRENDERON_PT_panel)

def unregister():
    bpy.utils.unregister_class(SEND_TO_BRENDERON_OT_send)
    bpy.utils.unregister_class(SEND_TO_BRENDERON_PT_panel)

if __name__ == "__main__":
    register()