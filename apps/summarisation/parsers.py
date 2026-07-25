import json

class SummaryParseError(Exception):
    pass

def parse_summary(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    
    # Strip markdown code fences
    if raw_text.startswith('```'):
        lines = raw_text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        raw_text = '\n'.join(lines)
        
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise SummaryParseError(f"Invalid JSON: {e}")
        
    required_keys = {'key_points', 'exam_flags', 'action_items', 'flashcards', 'summary_paragraph'}
    if not isinstance(data, dict):
        raise SummaryParseError("Parsed JSON is not a dictionary")
        
    if not required_keys.issubset(data.keys()):
        missing = required_keys - data.keys()
        raise SummaryParseError(f"Missing required keys: {missing}")
        
    return data

def parse_starter_questions(raw_text: str) -> list:
    raw_text = raw_text.strip()
    
    # Strip markdown code fences
    if raw_text.startswith('```'):
        lines = raw_text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        raw_text = '\n'.join(lines)
        
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise SummaryParseError(f"Invalid JSON: {e}")
        
    if not isinstance(data, list):
        raise SummaryParseError("Parsed JSON is not a list")
        
    return [str(q) for q in data][:3]
