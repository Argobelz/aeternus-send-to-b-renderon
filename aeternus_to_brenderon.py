bl_info = {
    "name": "Send to B-Renderon",
    "author": "Aeternus + Grok",
    "version": (1, 4, 9),
    "blender": (5, 0, 0),
    "location": "Properties > Output > Send to B-Renderon",
    "description": "Camera-specific SH folders and filenames (B=base, C=base+1, P=base+2)",
    "category": "Render",
}

import bpy
import json
import os
import re
from pathlib import Path
from datetime import datetime

QUEUE_NAME = "Default"

def get_blend_prefix(blend_path):
    stem = os.path.splitext(os.path.basename(blend_path))[0].upper()
    for p in ("PNT", "TXT", "VID"):
        if stem.startswith(p):
            return p
    return None

def get_camera_ranges(scene):
    markers = [m for m in scene.timeline_markers if m.camera]
    markers.sort(key=lambda m: m.frame)
    ranges = []
    for i, m in enumerate(markers):
        start = m.frame
        end = markers[i+1].frame - 1 if i + 1 < len(markers) else scene.frame_end
        camera_name = m.camera.name.strip() if m.camera else ""
        ranges.append({"camera": camera_name, "start": start, "end": end})
    return ranges

def build_output_info(blend_path, view_layer, camera):
    blend_file = Path(blend_path)
    blend_name = blend_file.stem.upper()
    
    # Extract base SQ and SH from blend name
    sq_match = re.search(r'SQ(\d+)', blend_name)
    sh_base_match = re.search(r'SH(\d+)', blend_name)
    
    sq = sq_match.group(1) if sq_match else "01"
    sh_base = int(sh_base_match.group(1)) if sh_base_match else 3
    
    # Camera-specific SH offset
    cam = str(camera).upper().strip() if camera else "B"
    offset = {"B": 0, "C": 1, "P": 2}.get(cam, 0)
    sh = sh_base + offset
    sh_str = f"{sh:03d}"  # 003, 004, 005...
    
    base = r"J:\Aeternus\Render\Img Seq\Phase 1\EPS002"
    ruta_output = f"{base}\\SQ{sq}\\SH{sh_str}"
    
    # Update SH in the filename too
    clean_name = re.sub(r'^(PNT|TXT|VID)_', '', blend_name)
    clean_name = re.sub(r'SH\d+', f'SH{sh_str}', clean_name)
    
    nombre_output = f"{view_layer}_{clean_name}_" if view_layer else f"{clean_name}_"
    
    scene_output = f"{ruta_output}\\{nombre_output}"
    
    patron = {
        "aplicar_a": 2,
        "ruta": ["J:\\Aeternus", "\\Render", "\\Img Seq", "\\Phase 1", "\\EPS002", f"\\SQ{sq}", f"\\SH{sh_str}"],
        "nombre": ["[VIEWLAYER_NAME]", "[CAMERA_NAME]", "_"] if cam else ["[VIEWLAYER_NAME]", "_"],
        "ruta_nodos": ruta_output,
        "nombre_nodos": nombre_output.rstrip('_'),
        "separador": "_"
    }
    
    return {
        "ruta_output": ruta_output,
        "nombre_output": nombre_output,
        "scene_output": scene_output,
        "ruta_frame_output": f"{ruta_output}\\{nombre_output}0001.tif",
        "patron_nombrado": patron,
        "nombrado": f"{ruta_output}\\{nombre_output}"
    }


class SEND_TO_BRENDERON_OT_send(bpy.types.Operator):
    bl_idname = "send_to_brenderon.send"
    bl_label = "Send Jobs to B-Renderon"
    bl_description = "Send with camera-specific SH (v1.4.9)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Save the .blend file first!")
            return {'CANCELLED'}

        blend_file = Path(blend_path)
        blend_folder = str(blend_file.parent)

        prefix = get_blend_prefix(blend_path)
        jobs = []
        view_layers = [vl.name for vl in scene.view_layers if vl.use]
        ranges = get_camera_ranges(scene) if prefix in ("PNT", "TXT") else []

        self.report({'INFO'}, f"Blend: {blend_file.name} | View Layers: {len(view_layers)} | Camera Ranges: {len(ranges)}")

        for vl_name in view_layers:
            if ranges:
                for r in ranges:
                    info = build_output_info(blend_path, vl_name, r["camera"])
                    jobs.append(self.create_job(blend_folder, blend_file.name, scene, vl_name, r["camera"], r["start"], r["end"], info))
            else:
                cam = scene.camera.name if scene.camera else ""
                info = build_output_info(blend_path, vl_name, cam)
                jobs.append(self.create_job(blend_folder, blend_file.name, scene, vl_name, cam, scene.frame_start, scene.frame_end, info))

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

            self.report({'INFO'}, f"✅ Sent {len(jobs)} jobs. Close & reopen B-Renderon.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error: {e}")
            return {'CANCELLED'}

    def create_job(self, ruta_blend, nombre_blend, scene, view_layer, camera, inicio, fin, info):
        return {
            "ruta_blend": ruta_blend,
            "nombre_blend": nombre_blend,
            "tag_blender": "Default",
            "modo": "Animation",
            "escena": scene.name,
            "view_layer": view_layer,
            "camara": camera,
            "inicio": str(inicio),
            "fin": str(fin),
            "step": "1",
            "args_extra": "",
            "nombres_dispositivos": "",
            "frames": "",
            "script": "",
            "estado": "no_comenzado",
            **info,
            "propiedades_argumentar": ["view_layer", "camara", "inicio", "nombrado", "fin"],
            "view_layers": [view_layer],
            "manejar_compositing": "auto",
            "camaras": [camera] if camera else [],
            "desactivado": False,
            "parallel_gpu": False,
            "job_id": f"blender_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        }


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
            layout.label(text="Save .blend first", icon='ERROR')
            return

        blend_file = Path(blend_path)
        layout.label(text=f"Folder: {blend_file.parent.name}", icon='FILE_FOLDER')
        layout.label(text=f"File: {blend_file.name}", icon='FILE_BLEND')
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