"""Schema Validator for Animation JSON specifications."""

import os
import json
import jsonschema


SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas", "animation_schema.json")


class SchemaValidator:
    _schema = None

    @classmethod
    def load_schema(cls):
        if cls._schema is None:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                cls._schema = json.load(f)
        return cls._schema

    @classmethod
    def validate_animation_plan(cls, plan_dict):
        """
        Validates an animation plan dictionary against the schema.
        Returns: (is_valid: bool, errors: list[str])
        """
        schema = cls.load_schema()
        validator = jsonschema.Draft7Validator(schema)
        errors = [err.message for err in validator.iter_errors(plan_dict)]
        return len(errors) == 0, errors
