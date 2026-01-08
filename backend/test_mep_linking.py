#!/usr/bin/env python3
"""
Test MEP name linking directly to debug pattern matching issues.
"""
import re
from typing import Dict

# Sample MEP data (uppercase keys as in the real implementation)
mep_data = {
    'ANTONIO DECARO': {
        'mep_id': '257122',
        'name': 'Antonio DECARO',
        'url': 'https://www.europarl.europa.eu/meps/en/257122/Antonio+DECARO/home'
    },
    'PASCAL CANFIN': {
        'mep_id': '96711',
        'name': 'Pascal CANFIN',
        'url': 'https://www.europarl.europa.eu/meps/en/96711/Pascal+CANFIN/home'
    },
    'CÉSAR LUENA': {
        'mep_id': '197717',
        'name': 'César LUENA',
        'url': 'https://www.europarl.europa.eu/meps/en/197717/C%C3%A9sar+LUENA/home'
    }
}

# Sample AI responses to test
test_responses = [
    "**Antonio DECARO** (S&D, Italy) serves as the Chair.",
    "The committee is chaired by Antonio DECARO from Italy.",
    "Pascal CANFIN is one of the Vice-Chairs.",
    "Members include César LUENA and Antonio DECARO.",
    "Antonio Decaro leads the committee.",  # lowercase version
]

def linkify_mep_names(text: str, mep_data: Dict[str, Dict[str, str]]) -> str:
    """Post-process AI response to add markdown links for MEP names."""
    if not mep_data:
        return text

    # Sort MEP names by length (longest first) to avoid partial matches
    sorted_names = sorted(mep_data.keys(), key=len, reverse=True)

    links_added = 0
    for name_key in sorted_names:
        mep_info = mep_data[name_key]
        name = mep_info['name']
        url = mep_info['url']

        # Split name into parts for flexible matching
        name_parts = name.split()

        if len(name_parts) >= 2:
            # Match full name with flexible spacing and optional markdown
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])

            # Pattern: optional **, then first name, space(s), last name, optional **
            # Use word boundaries to avoid matching inside other words
            pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + re.escape(first_name) + r')\s+(' + re.escape(last_name) + r')\b\*{0,2}(?!\]\()'

            # Replacement: preserve any found text structure but wrap in link
            def replace_func(match):
                nonlocal links_added
                matched_text = match.group(0)
                # Remove any markdown bold from the matched text
                cleaned_text = matched_text.replace('**', '')
                links_added += 1
                return f'[{cleaned_text}]({url})'

            text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)
        else:
            # Single name (edge case)
            pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + re.escape(name) + r')\b\*{0,2}(?!\]\()'

            def replace_func(match):
                nonlocal links_added
                matched_text = match.group(0)
                cleaned_text = matched_text.replace('**', '')
                links_added += 1
                return f'[{cleaned_text}]({url})'

            text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)

    if links_added > 0:
        print(f"✓ Added {links_added} MEP profile links")
    else:
        print(f"✗ No MEP names found to link despite having {len(mep_data)} MEP profiles")

    return text

if __name__ == "__main__":
    print("=" * 70)
    print("Testing MEP Name Linking")
    print("=" * 70)
    print(f"\nMEP Database has {len(mep_data)} profiles:")
    for key, data in mep_data.items():
        print(f"  - {key} → {data['name']}")

    print("\n" + "=" * 70)
    print("Testing different response formats:")
    print("=" * 70)

    for i, response in enumerate(test_responses, 1):
        print(f"\n[Test {i}]")
        print(f"Original: {response}")
        result = linkify_mep_names(response, mep_data)
        print(f"Result:   {result}")
        print()
