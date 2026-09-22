#!/usr/bin/env python3
"""Offline interface example, not a model evaluation or competitive solver.

Replace the response construction with your own tool-free harness. Send only
request['messages'] to its model. Model settings are separate from those messages.
The two arguments are supplied by `exam.py run --adapter command`.
"""
import json
from pathlib import Path
import sys

request_path, response_path = map(Path, sys.argv[1:])
request = json.loads(request_path.read_text())
response = {
    'answer': None,  # A completed invalid answer demonstrates a permanent zero.
    'finish_reason': 'stop',
    'response_model': 'offline-interface-example',
    'usage': {'input_tokens': None, 'output_tokens': None},
    'usage_complete': False,
}
response_path.write_text(json.dumps(response) + '\n')
