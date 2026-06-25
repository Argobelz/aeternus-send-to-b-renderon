bl_info = {
    "name": "Send to B-Renderon",
    "author": "Aeternus",
    "version": (1, 9, 0),
    "blender": (5, 0, 0),
    "location": "Properties > Output > Send to B-Renderon",
    "description": "Checkbox selection for VID view layers and PNT cameras (v1.9.0)",
    "category": "Render",
}

import bpy
import json
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime

QUEUE_NAME = "Default"

# ---------------------------------------------------------------------------
# Scene property groups
# ---------------------------------------------------------------------------

class VIDViewLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    camera: bpy.props.StringProperty()
    enabled: bpy.props.BoolProperty(default=True)


class PNTCameraItem(bpy.types.PropertyGroup):
    camera: bpy.props.StringProperty()
    start: bpy.props.IntProperty()
    end: bpy.props.IntProperty()
    enabled: bpy.props.BoolProperty(default=True)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def get_blend_prefix(blend_path):
    stem = os.path.splitext(os.path.basename(blend_path))[0].upper()
    for p in ("PNT", "TXT", "VID"):
        if stem.startswith(p):
            return p
    return None


def extract_eps_sq_sh(camera_name):
    cam_str = str(camera_name).upper()
    eps_match = re.search(r'EPS(\d+)', cam_str)
    sq_match  = re.search(r'SQ(\d+)',  cam_str)
    sh_match  = re.search(r'SH(\d+)',  cam_str)
    eps = (eps_match.group(1) if eps_match else "002").zfill(3)
    sq  = sq_match.group(1)  if sq_match  else "01"
    sh  = sh_match.group(1)  if sh_match  else "003"
    return eps, sq, sh


def find_camera_in_layer_collection(layer_col):
    for obj in layer_col.collection.objects:
        if obj.type == 'CAMERA':
            return obj.name
    for child in layer_col.children:
        if not child.exclude:
            result = find_camera_in_layer_collection(child)
            if result:
                return result
    return None


def get_vl_camera(vl, scene):
    cam_obj = getattr(vl, "camera", None)
    if cam_obj:
        return cam_obj.name.strip()
    camera_name = find_camera_in_layer_collection(vl.layer_collection)
    if camera_name:
        return camera_name
    if scene.camera:
        return scene.camera.name.strip()
    return ""


def get_camera_ranges(scene):
    markers = [m for m in scene.timeline_markers if m.camera]
    markers.sort(key=lambda m: m.frame)
    ranges = []
    for i, m in enumerate(markers):
        start = m.frame
        end = markers[i+1].frame - 1 if i + 1 < len(markers) else scene.frame_end
        ranges.append({
            "camera": m.camera.name.strip() if m.camera else "",
            "start": start,
            "end": end,
        })
    return ranges


def build_output_info(blend_path, view_layer, camera):
    blend_name = Path(blend_path).stem.upper()
    eps_num, sq, sh_str = extract_eps_sq_sh(camera)
    vl_name = str(view_layer).strip()
    cam_name_clean = str(camera).strip()

    print(f"[DEBUG] Blend: {blend_name} | VL: {vl_name} | Camera: {cam_name_clean} | EPS: {eps_num} | SQ: {sq} | SH: {sh_str}")

    base = r"J:\Aeternus\Render\Img Seq\Phase 1"
    ruta_output = f"{base}\\EPS{eps_num}\\SQ{sq}\\SH{sh_str}"

    # Prepend view layer initial as file prefix (e.g. B_, C_, P_)
    vl_initial = vl_name[0].upper() if vl_name else ""
    file_prefix = f"{vl_initial}_" if vl_initial else ""
    nombre_output = f"{file_prefix}{cam_name_clean}_"

    patron = {
        "aplicar_a": 2,
        "ruta": [
            "J:\\Aeternus", "\\Render", "\\Img Seq", "\\Phase 1",
            f"\\EPS{eps_num}", f"\\SQ{sq}", f"\\SH{sh_str}"
        ],
        "nombre": ["[CAMERA_NAME]", f"{file_prefix}{cam_name_clean}", "_"],
        "ruta_nodos": ruta_output,
        "nombre_nodos": f"{file_prefix}{cam_name_clean}",
        "separador": "_",
    }

    return {
        "ruta_output": ruta_output,
        "nombre_output": nombre_output,
        "scene_output": f"{ruta_output}\\{nombre_output}",
        "ruta_frame_output": f"{ruta_output}\\{nombre_output}0001.tif",
        "patron_nombrado": patron,
        "nombrado": f"{ruta_output}\\{nombre_output}",
    }


def write_jobs_to_queue(jobs):
    queue_file = Path(r"D:\B-Renderon\queues") / f"{QUEUE_NAME}.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if queue_file.exists():
        with open(queue_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    for job in jobs:
        lines.append(json.dumps(job, ensure_ascii=False) + "\n")
    tmp_fd, tmp_path = tempfile.mkstemp(dir=queue_file.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        os.replace(tmp_path, queue_file)
    except Exception:
        os.unlink(tmp_path)
        raise


def make_job(blend_folder, blend_name, scene, view_layer, camera, inicio, fin, info):
    return {
        "ruta_blend": blend_folder,
        "nombre_blend": blend_name,
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


# ---------------------------------------------------------------------------
# Operators — refresh lists
# ---------------------------------------------------------------------------

class SEND_TO_BRENDERON_OT_refresh_vid(bpy.types.Operator):
    bl_idname = "send_to_brenderon.refresh_vid"
    bl_label = "Refresh VID list"

    def execute(self, context):
        scene = context.scene
        scene.btb_vid_layers.clear()
        for vl in scene.view_layers:
            if not vl.use:
                continue
            camera = get_vl_camera(vl, scene)
            item = scene.btb_vid_layers.add()
            item.name = vl.name
            item.camera = camera
            item.enabled = True
        return {'FINISHED'}


class SEND_TO_BRENDERON_OT_refresh_pnt(bpy.types.Operator):
    bl_idname = "send_to_brenderon.refresh_pnt"
    bl_label = "Refresh PNT list"

    def execute(self, context):
        scene = context.scene
        scene.btb_pnt_cameras.clear()
        for r in get_camera_ranges(scene):
            item = scene.btb_pnt_cameras.add()
            item.camera = r["camera"]
            item.start = r["start"]
            item.end = r["end"]
            item.enabled = True
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operators — select all / none
# ---------------------------------------------------------------------------

class SEND_TO_BRENDERON_OT_vid_select_all(bpy.types.Operator):
    bl_idname = "send_to_brenderon.vid_select_all"
    bl_label = "All"
    def execute(self, context):
        for item in context.scene.btb_vid_layers:
            item.enabled = True
        return {'FINISHED'}

class SEND_TO_BRENDERON_OT_vid_select_none(bpy.types.Operator):
    bl_idname = "send_to_brenderon.vid_select_none"
    bl_label = "None"
    def execute(self, context):
        for item in context.scene.btb_vid_layers:
            item.enabled = False
        return {'FINISHED'}

class SEND_TO_BRENDERON_OT_pnt_select_all(bpy.types.Operator):
    bl_idname = "send_to_brenderon.pnt_select_all"
    bl_label = "All"
    def execute(self, context):
        for item in context.scene.btb_pnt_cameras:
            item.enabled = True
        return {'FINISHED'}

class SEND_TO_BRENDERON_OT_pnt_select_none(bpy.types.Operator):
    bl_idname = "send_to_brenderon.pnt_select_none"
    bl_label = "None"
    def execute(self, context):
        for item in context.scene.btb_pnt_cameras:
            item.enabled = False
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator — send selected jobs
# ---------------------------------------------------------------------------

class SEND_TO_BRENDERON_OT_send(bpy.types.Operator):
    bl_idname = "send_to_brenderon.send"
    bl_label = "Send Selected Jobs"
    bl_description = "Send checked jobs to B-Renderon queue (v1.9.0)"
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

        if prefix == "VID":
            if not scene.btb_vid_layers:
                self.report({'ERROR'}, "Click Refresh first to load view layers.")
                return {'CANCELLED'}
            for item in scene.btb_vid_layers:
                if not item.enabled:
                    continue
                if not item.camera:
                    self.report({'WARNING'}, f"No camera for '{item.name}', skipping.")
                    continue
                info = build_output_info(blend_path, item.name, item.camera)
                jobs.append(make_job(
                    blend_folder, blend_file.name, scene,
                    item.name, item.camera,
                    scene.frame_start, scene.frame_end, info
                ))

        elif prefix == "PNT":
            if not scene.btb_pnt_cameras:
                self.report({'ERROR'}, "Click Refresh first to load camera ranges.")
                return {'CANCELLED'}
            view_layers = [vl for vl in scene.view_layers if vl.use]
            for item in scene.btb_pnt_cameras:
                if not item.enabled:
                    continue
                for vl in view_layers:
                    info = build_output_info(blend_path, vl.name, item.camera)
                    jobs.append(make_job(
                        blend_folder, blend_file.name, scene,
                        vl.name, item.camera,
                        item.start, item.end, info
                    ))

        elif prefix == "TXT":
            ranges = get_camera_ranges(scene)
            view_layers = [vl for vl in scene.view_layers if vl.use]
            for r in ranges:
                for vl in view_layers:
                    info = build_output_info(blend_path, vl.name, r["camera"])
                    jobs.append(make_job(
                        blend_folder, blend_file.name, scene,
                        vl.name, r["camera"],
                        r["start"], r["end"], info
                    ))

        else:
            cam = scene.camera.name if scene.camera else ""
            for vl in (vl for vl in scene.view_layers if vl.use):
                info = build_output_info(blend_path, vl.name, cam)
                jobs.append(make_job(
                    blend_folder, blend_file.name, scene,
                    vl.name, cam,
                    scene.frame_start, scene.frame_end, info
                ))

        if not jobs:
            self.report({'ERROR'}, "No jobs selected. Check your checkboxes.")
            return {'CANCELLED'}

        try:
            write_jobs_to_queue(jobs)
            self.report({'INFO'}, f"✅ Sent {len(jobs)} jobs.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Queue write failed: {e}")
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

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
            layout.label(text="Save .blend first", icon='ERROR')
            return

        blend_file = Path(blend_path)
        prefix = get_blend_prefix(blend_path)

        layout.label(text=f"File: {blend_file.name}", icon='FILE_BLEND')
        layout.label(text=f"Prefix: {prefix or 'Unknown'}")
        layout.separator()

        # ---- VID panel ----
        if prefix == "VID":
            row = layout.row()
            row.label(text="View Layers")
            row.operator("send_to_brenderon.refresh_vid", text="Refresh", icon='FILE_REFRESH')

            if scene.btb_vid_layers:
                # Select all / none row
                row = layout.row(align=True)
                row.operator("send_to_brenderon.vid_select_all", icon='CHECKBOX_HLT')
                row.operator("send_to_brenderon.vid_select_none", icon='CHECKBOX_DEHLT')

                box = layout.box()
                for item in scene.btb_vid_layers:
                    row = box.row()
                    row.prop(item, "enabled", text="")
                    row.label(text=item.name)
                    row.label(text=item.camera if item.camera else "No camera", icon='CAMERA_DATA')
            else:
                layout.label(text="Click Refresh to load view layers", icon='INFO')

        # ---- PNT panel ----
        elif prefix == "PNT":
            row = layout.row()
            row.label(text="Camera Ranges")
            row.operator("send_to_brenderon.refresh_pnt", text="Refresh", icon='FILE_REFRESH')

            if scene.btb_pnt_cameras:
                row = layout.row(align=True)
                row.operator("send_to_brenderon.pnt_select_all", icon='CHECKBOX_HLT')
                row.operator("send_to_brenderon.pnt_select_none", icon='CHECKBOX_DEHLT')

                box = layout.box()
                for item in scene.btb_pnt_cameras:
                    row = box.row()
                    row.prop(item, "enabled", text="")
                    row.label(text=item.camera, icon='CAMERA_DATA')
                    row.label(text=f"f{item.start}–{item.end}")
            else:
                layout.label(text="Click Refresh to load camera ranges", icon='INFO')

        # ---- TXT / other — no selection UI needed ----
        else:
            layout.label(text="All camera ranges will be sent.", icon='INFO')

        layout.separator()
        layout.operator("send_to_brenderon.send", icon='RENDER_ANIMATION', text="Send Selected Jobs")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    VIDViewLayerItem,
    PNTCameraItem,
    SEND_TO_BRENDERON_OT_refresh_vid,
    SEND_TO_BRENDERON_OT_refresh_pnt,
    SEND_TO_BRENDERON_OT_vid_select_all,
    SEND_TO_BRENDERON_OT_vid_select_none,
    SEND_TO_BRENDERON_OT_pnt_select_all,
    SEND_TO_BRENDERON_OT_pnt_select_none,
    SEND_TO_BRENDERON_OT_send,
    SEND_TO_BRENDERON_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.btb_vid_layers = bpy.props.CollectionProperty(type=VIDViewLayerItem)
    bpy.types.Scene.btb_pnt_cameras = bpy.props.CollectionProperty(type=PNTCameraItem)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.btb_vid_layers
    del bpy.types.Scene.btb_pnt_cameras


if __name__ == "__main__":
    register()

