"""Master Timeline Manager.
Synchronizes visual scene durations with audio narration lengths so animation never cuts off early.
"""


class TimelineManager:
    @staticmethod
    def build_timeline(scenes, audio_results):
        """
        Creates an aligned master timeline.
        Audio duration dictates scene duration if audio is longer than target scene duration.
        """
        audio_map = {a["sceneId"]: a for a in audio_results}
        timeline = []
        current_time = 0.0

        for idx, scene in enumerate(scenes):
            scene_id = scene.get("id", f"scene_{idx+1:02d}")
            base_dur = float(scene.get("duration", 5.0))
            
            # If audio exists, ensure scene is at least audio duration + 0.5s padding
            audio_info = audio_map.get(scene_id)
            if audio_info:
                audio_dur = audio_info["duration"]
                actual_dur = max(base_dur, audio_dur + 0.5)
            else:
                actual_dur = base_dur

            entry = {
                "sceneId": scene_id,
                "type": scene.get("type", "EXPLANATION"),
                "visualMode": scene.get("visualMode", "2D"),
                "startTime": round(current_time, 2),
                "endTime": round(current_time + actual_dur, 2),
                "duration": round(actual_dur, 2),
                "narrationText": scene.get("narration", ""),
                "audioPath": audio_info["audioPath"] if audio_info else None
            }
            timeline.append(entry)
            current_time += actual_dur

        return {
            "totalDuration": round(current_time, 2),
            "timeline": timeline
        }
