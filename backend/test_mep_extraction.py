#!/usr/bin/env python3
"""
Test MEP data extraction from committee info to debug why mep_data might be empty.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ai.context_builder import ContextBuilder

async def test_mep_extraction():
    print("=" * 70)
    print("Testing MEP Data Extraction from Committee Info")
    print("=" * 70)

    # Initialize context builder
    context_builder = ContextBuilder()

    # Test query about ENVI committee
    test_query = "Who are the MEPs on the ENVI committee?"

    print(f"\nQuery: {test_query}")
    print("\nBuilding context...")

    try:
        # Build context
        context_data = await context_builder.build_context_for_query(
            user_message=test_query,
            conversation_history=[]
        )

        print(f"✓ Context built successfully")
        print(f"\nContext data attributes: {dir(context_data)}")

        # Check if committee_info exists
        if hasattr(context_data, 'committee_info'):
            print(f"\n✓ committee_info attribute exists")
            committee_info = context_data.committee_info
            print(f"  Type: {type(committee_info)}")
            print(f"  Length: {len(committee_info) if committee_info else 0}")

            if committee_info:
                print(f"\n  Committee data:")
                for i, committee in enumerate(committee_info):
                    print(f"\n  [{i+1}] Committee: {committee.get('code', 'N/A')}")
                    print(f"      Name: {committee.get('name', 'N/A')}")

                    members_by_role = committee.get('members_by_role', {})
                    print(f"      Roles: {list(members_by_role.keys())}")

                    total_members = sum(len(members) for members in members_by_role.values())
                    print(f"      Total members: {total_members}")

                    # Show first few members
                    for role, members in list(members_by_role.items())[:2]:
                        print(f"\n      {role}:")
                        for member in members[:3]:
                            print(f"        - {member.get('name', 'N/A')} (ID: {member.get('mep_id', 'N/A')})")
                        if len(members) > 3:
                            print(f"        ... and {len(members) - 3} more")

                # Now test extraction
                print("\n" + "=" * 70)
                print("Simulating _extract_mep_data()")
                print("=" * 70)

                mep_data = {}
                for committee in committee_info:
                    members_by_role = committee.get('members_by_role', {})

                    for role, members in members_by_role.items():
                        for member in members:
                            name = member.get('name', '')
                            mep_id = member.get('mep_id', '')

                            if name and mep_id:
                                key = name.upper()
                                url_name = name.replace(' ', '+')

                                mep_data[key] = {
                                    'mep_id': mep_id,
                                    'name': name,
                                    'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}/{url_name}/home"
                                }

                print(f"\n✓ Extracted {len(mep_data)} MEP profiles")

                if mep_data:
                    print(f"\nFirst 10 MEP names (keys):")
                    for i, key in enumerate(list(mep_data.keys())[:10], 1):
                        print(f"  {i}. {key} → {mep_data[key]['name']}")
                else:
                    print("\n✗ No MEP data extracted!")

            else:
                print("\n✗ committee_info is empty/None")
        else:
            print("\n✗ committee_info attribute does NOT exist on context_data")

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(test_mep_extraction())
