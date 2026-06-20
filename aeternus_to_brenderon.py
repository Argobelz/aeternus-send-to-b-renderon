bl_info = {
    "name": "Send to B-Renderon",
    "author": "Argobelz (adapted from Aeternus)",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "Properties > Output > Send to B-Renderon",
    "description": "Sends render jobs to B-Renderon queue manager",
    "category": "Render",
}

import bpy
import json
import re
import os
import subprocess
import time

# B-Renderon paths
B_RENDERON_PATH = r"D:\B-Renderon\B-renderon.exe"
QUEUE_DIR = r"D:\B-Renderon\queues"
DEFAULT_QUEUE = "Default.json"

RENDER_ROOT = r"J:\Aeternus\Render\Img Seq"
FILE_PREFIXES = ("PNT", "TXT", "VID")

# ... (full code as previously generated)