"""Explicit opt-in bridge to Form Engine's extracted binary packing contract.

The human Blueprint, face/body equations, scene assembly and validators remain
owned by Character Editor. No dependency is imported on the builtin path.
"""
from __future__ import annotations


def create_buffer_builder():
    try:
        from axm_form_engine.gltf_buffer import (
            BUFFER_API,
            GltfBufferBuilder,
            buffer_provenance,
        )
    except ImportError as exc:
        raise ValueError(
            "The form-engine buffer backend needs an installed AXM Form Engine "
            "with glTF buffer support (G1). Install its local checkout first. "
            "Use --buffer-backend builtin to use the existing writer."
        ) from exc
    if BUFFER_API != "axm.form.gltf-buffer/v0.1":
        raise ValueError(f"unsupported Form Engine buffer contract: {BUFFER_API!r}")

    class CharacterBufferAdapter(GltfBufferBuilder):
        # The existing scene writer uses this private name. Keep it in the
        # adapter instead of exporting a donor-private API from Form Engine.
        def _align(self, n=4):
            if n != 4:
                raise ValueError("the Form Engine buffer contract uses four-byte alignment")
            self.align()

    return CharacterBufferAdapter(), buffer_provenance()
