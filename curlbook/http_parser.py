def parse_http(text: str):
    """Parse a .http string into a list of request dictionaries.

    Each dictionary has keys: method, url, headers, body.
    """
    requests = []
    # Split by the delimiter '###' (with optional whitespace) that separates requests
    # We'll split on lines that start with '###' after stripping whitespace.
    sections = []
    current = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('###'):
            if current:
                sections.append('\n'.join(current))
                current = []
        else:
            current.append(line)
    if current:
        sections.append('\n'.join(current))

    for section in sections:
        if not section.strip():
            continue
        # Parse the section into method, url, headers, body
        lines = section.splitlines()
        if not lines:
            continue
        # First line: method and url
        parts = lines[0].split()
        if len(parts) < 2:
            # Skip invalid
            continue
        method = parts[0]
        url = parts[1]
        headers = {}
        body = []
        i = 1
        # Parse headers until an empty line
        while i < len(lines):
            line = lines[i]
            if line.strip() == '':
                i += 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
            i += 1
        # The rest is the body (could be empty)
        body_lines = lines[i:]
        body = '\n'.join(body_lines)
        requests.append({
            'method': method,
            'url': url,
            'headers': headers,
            'body': body,
        })
    return requests