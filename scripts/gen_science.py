#!/usr/bin/env python3
"""
Generate ~20,000 science knowledge entries across 7 domains.
Output: gen_science_01.json through gen_science_08.json in data/knowledge/generated/
"""
import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SOURCE = "generated_knowledge"

def entry(content, typ, tags):
    return {"content": content, "type": typ, "tags": tags, "source": SOURCE}

all_entries = []
