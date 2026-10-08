"""Validates Lesson JSON + Solution Pack for the Remotion/Three.js pipeline."""

from .schema_validator import SchemaValidator


REQUIRED_SOLUTION_FIELDS = [
    "concept",
    "given",
    "find",
    "formula",
    "steps",
    "answer",
    "equationBeats",
    "intuition",
    "simulation",
]


class LessonValidator:
    @staticmethod
    def validate_solution_pack(solution):
        errors = []
        if not isinstance(solution, dict):
            return False, ["solution must be an object"]
        for key in REQUIRED_SOLUTION_FIELDS:
            if key not in solution:
                errors.append(f"missing solution.{key}")
        steps = solution.get("steps") or []
        if steps and not isinstance(steps[0], dict):
            errors.append("solution.steps should be objects with explanation/formula/visualCue")
        beats = solution.get("equationBeats") or []
        if solution.get("requiredCalculation", True) and not beats and not solution.get("formula"):
            errors.append("solution needs equationBeats or formula for calculation scenes")
        return len(errors) == 0, errors

    @staticmethod
    def validate_lesson(plan):
        ok, schema_errors = SchemaValidator.validate_animation_plan(plan)
        errors = list(schema_errors or [])
        scenes = plan.get("scenes") or []
        if len(scenes) < 4:
            errors.append("lesson should contain at least 4 teaching scenes")
        for scene in scenes:
            if not scene.get("narration"):
                errors.append(f"{scene.get('id', '?')}: missing narration")
            if "onScreen" not in scene:
                errors.append(f"{scene.get('id', '?')}: missing onScreen teaching payload")
        sol_ok, sol_errors = LessonValidator.validate_solution_pack(plan.get("solution") or {})
        if not sol_ok:
            errors.extend(sol_errors)
        return len(errors) == 0, errors
