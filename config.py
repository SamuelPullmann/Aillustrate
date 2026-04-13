from config_local import *

# Model configurations
TEXT_MODEL = "gemini-3.1-pro-preview"
IMAGE_MODELS = [
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image"
]
IMAGE_MODEL = IMAGE_MODELS[0]
VERTEX_LOCATION = "global"

# Analysis and Generation Limits
MAX_ANALYZE_CHAPTERS = 1  # 0 means infinite (analyze all chapters)
MAX_SCENES_PER_CHAPTER = 2 # 0 means infinite

# Analysis phase switches
ANALYZE_CHARACTERS = True
ANALYZE_SCENES = True
ANALYZE_ENVIRONMENTS = True  # ANALYZE_SCENES must be True for this to be effective


