"""Stable video generation defaults."""

VIDEO_MODEL_ID = "volcano.seedance.2_0"
MAX_PROVIDER_SEED = 2_147_483_647
PROVIDER_VIDEO_WATERMARK_ENABLED = False
PROVIDER_VIDEO_WATERMARK_ARG = "true" if PROVIDER_VIDEO_WATERMARK_ENABLED else "false"
SEEDANCE_NATIVE_AUDIO_MODEL_IDS = frozenset({"doubao-seedance-1-5-pro-251215"})
