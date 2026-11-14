"""Regenerate a session text entity without embedding editor metadata in Gerber."""

from dataclasses import asdict, replace

from gerber_editor.tools.vector_text import vector_text


def text_objects(layer, entity, polarity):
    values = asdict(entity)
    values.pop("group_id")
    values["position"] = entity.position
    return [
        replace(obj, text_entity=entity) for obj in vector_text(layer, **values, polarity=polarity)
    ]
