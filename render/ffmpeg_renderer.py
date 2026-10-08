"""Thin re-export of FFmpeg composition utilities."""

from video.compositor import VideoCompositor
from video.ffmpeg import FFmpegUtils

__all__ = ["VideoCompositor", "FFmpegUtils"]
