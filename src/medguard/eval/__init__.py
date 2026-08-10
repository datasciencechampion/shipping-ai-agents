"""MedGuard evaluation harness (v1).

The first thing we add on the road out of the demo: a way to *measure* whether
MedGuard is right — before we touch anything else. This package provides a
golden-set scorer that deliberately reports metrics **stratified by severity**,
so a high headline accuracy can't hide a catastrophic safety tail.
"""
