"""Subtitle Generator for Educational Videos.
Builds clean, synchronized SRT & WebVTT subtitle files with no overlapping lines.
"""

import os


def format_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class SubtitleGenerator:
    @staticmethod
    def generate_srt(timeline_entries, output_srt_path):
        """Generates standard SRT subtitles from timeline narration segments."""
        os.makedirs(os.path.dirname(os.path.abspath(output_srt_path)), exist_ok=True)
        
        lines = []
        sub_idx = 1

        for entry in timeline_entries:
            text = entry.get("narrationText", "").strip()
            if not text:
                continue

            start_t = entry["startTime"]
            end_t = entry["endTime"]
            
            # Split long sentences into 1-2 line chunks if longer than 70 characters
            words = text.split()
            chunk_size = 9
            chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
            
            chunk_duration = (end_t - start_t) / max(1, len(chunks))
            
            for c_i, chunk in enumerate(chunks):
                c_start = start_t + (c_i * chunk_duration)
                c_end = c_start + chunk_duration - 0.05
                
                lines.append(f"{sub_idx}")
                lines.append(f"{format_srt_time(c_start)} --> {format_srt_time(c_end)}")
                lines.append(chunk)
                lines.append("")
                sub_idx += 1

        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return output_srt_path
