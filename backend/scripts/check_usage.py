#!/usr/bin/env python3
"""
Check Brubru Usage Statistics

Run from backend directory:
    python -m scripts.check_usage

Or with specific days:
    python -m scripts.check_usage --days 7
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import engine


def check_usage(days: int = 7):
    """Check usage statistics for the last N days using raw SQL."""
    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=days)
    cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

    print(f"\n{'='*60}")
    print(f"  BRUBRU USAGE REPORT - Last {days} days")
    print(f"  Period: {cutoff_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    with engine.connect() as conn:
        # 1. User Activity
        print("1. USER ACTIVITY")
        print("-" * 40)

        # Total users
        result = conn.execute(text("SELECT COUNT(*) FROM users"))
        total_users = result.scalar()
        print(f"   Total registered users: {total_users}")

        # Active users
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM users
            WHERE last_login >= '{cutoff_str}'
        """))
        active_users = result.scalar()
        print(f"   Users logged in (last {days} days): {active_users}")

        # Users by subscription tier
        result = conn.execute(text("""
            SELECT COALESCE(subscription_tier, 'white') as tier, COUNT(*)
            FROM users
            GROUP BY subscription_tier
            ORDER BY COUNT(*) DESC
        """))
        print(f"\n   Users by tier:")
        for tier, count in result:
            print(f"     - {tier}: {count}")

        # Recently active users
        result = conn.execute(text(f"""
            SELECT
                COALESCE(full_name, first_name, email) as name,
                email,
                subscription_tier,
                last_login
            FROM users
            WHERE last_login >= '{cutoff_str}'
            ORDER BY last_login DESC
            LIMIT 15
        """))
        rows = result.fetchall()
        if rows:
            print(f"\n   Recent logins:")
            for name, email, tier, last_login in rows:
                display_name = (name or email or 'Unknown')[:35]
                tier_str = tier or 'white'
                login_str = last_login.strftime('%Y-%m-%d %H:%M') if last_login else 'Never'
                print(f"     - {display_name:<35} [{tier_str:6}] {login_str}")

        # 2. Chat Analytics (AI Usage)
        print(f"\n\n2. AI USAGE (Chat Analytics)")
        print("-" * 40)

        # Check if chat_analytics table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'chat_analytics'
            )
        """))
        has_analytics = result.scalar()

        if has_analytics:
            result = conn.execute(text(f"""
                SELECT
                    COUNT(*) as total_messages,
                    COALESCE(SUM(tokens_used), 0) as total_tokens,
                    COALESCE(AVG(tokens_used), 0) as avg_tokens,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time
                FROM chat_analytics
                WHERE created_at >= '{cutoff_str}'
            """))
            row = result.fetchone()
            if row and row[0] > 0:
                total_messages, total_tokens, avg_tokens, avg_response_time = row
                print(f"   Total AI messages: {total_messages:,}")
                print(f"   Total tokens used: {int(total_tokens):,}")
                print(f"   Avg tokens/message: {avg_tokens:,.0f}")
                print(f"   Avg response time: {avg_response_time:,.0f}ms")

                # Estimate cost (Claude pricing: ~$3/1M input, ~$15/1M output tokens)
                if total_tokens:
                    input_tokens = total_tokens * 0.3
                    output_tokens = total_tokens * 0.7
                    estimated_cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)
                    print(f"\n   Estimated API cost: ${estimated_cost:,.2f} (rough estimate)")
                    print(f"   Daily average: ${estimated_cost/days:,.2f}/day")

                # Provider breakdown
                result = conn.execute(text(f"""
                    SELECT
                        COALESCE(provider, 'Unknown') as provider,
                        COUNT(*) as count,
                        COALESCE(SUM(tokens_used), 0) as tokens
                    FROM chat_analytics
                    WHERE created_at >= '{cutoff_str}'
                    GROUP BY provider
                    ORDER BY count DESC
                """))
                rows = result.fetchall()
                if rows:
                    print(f"\n   By AI provider:")
                    for provider, count, tokens in rows:
                        print(f"     - {provider}: {count:,} messages, {int(tokens):,} tokens")
            else:
                print("   No chat analytics data found for this period.")
        else:
            print("   [chat_analytics table not found]")

        # 3. Chat Conversations
        print(f"\n\n3. CHAT CONVERSATIONS")
        print("-" * 40)

        # Check if chats table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'chats'
            )
        """))
        has_chats = result.scalar()

        if has_chats:
            result = conn.execute(text(f"""
                SELECT
                    COUNT(*) as total_chats,
                    COALESCE(SUM(message_count), 0) as total_messages,
                    COALESCE(SUM(total_tokens_used), 0) as total_tokens
                FROM chats
                WHERE created_at >= '{cutoff_str}'
            """))
            row = result.fetchone()
            if row and row[0] > 0:
                total_chats, total_messages, total_tokens = row
                print(f"   New conversations: {total_chats:,}")
                print(f"   Total messages: {int(total_messages):,}")
                print(f"   Total tokens: {int(total_tokens):,}")
            else:
                print("   No new conversations in this period.")
        else:
            print("   [chats table not found]")

        # 4. Most Active Users (by analytics)
        print(f"\n\n4. MOST ACTIVE USERS (by AI messages)")
        print("-" * 40)

        if has_analytics:
            result = conn.execute(text(f"""
                SELECT
                    COALESCE(u.full_name, u.first_name, u.email) as name,
                    u.email,
                    COALESCE(u.subscription_tier, 'white') as tier,
                    COUNT(ca.id) as message_count,
                    COALESCE(SUM(ca.tokens_used), 0) as total_tokens
                FROM chat_analytics ca
                JOIN users u ON ca.user_id = u.id
                WHERE ca.created_at >= '{cutoff_str}'
                GROUP BY u.id, u.full_name, u.first_name, u.email, u.subscription_tier
                ORDER BY message_count DESC
                LIMIT 15
            """))
            rows = result.fetchall()
            if rows:
                for name, email, tier, msg_count, tokens in rows:
                    display_name = (name or email or 'Unknown')[:30]
                    print(f"     - {display_name:<30} [{tier:6}]: {msg_count:,} msgs, {int(tokens):,} tokens")
            else:
                print("   No user activity data found.")
        else:
            print("   [chat_analytics table not found]")

        # 5. Daily Breakdown
        print(f"\n\n5. DAILY ACTIVITY")
        print("-" * 40)

        if has_analytics:
            result = conn.execute(text(f"""
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as messages,
                    COALESCE(SUM(tokens_used), 0) as tokens,
                    COUNT(DISTINCT user_id) as unique_users
                FROM chat_analytics
                WHERE created_at >= '{cutoff_str}'
                GROUP BY DATE(created_at)
                ORDER BY date
            """))
            rows = result.fetchall()
            if rows:
                print(f"   {'Date':<12} {'Messages':>10} {'Tokens':>12} {'Users':>8}")
                print(f"   {'-'*12} {'-'*10} {'-'*12} {'-'*8}")
                for date, messages, tokens, users in rows:
                    print(f"   {str(date):<12} {messages:>10,} {int(tokens):>12,} {users:>8}")
            else:
                print("   No daily activity data found.")
        else:
            print("   [chat_analytics table not found]")

        # 6. Document Generation (if applicable)
        print(f"\n\n6. DOCUMENT GENERATION")
        print("-" * 40)

        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'user_documents'
            )
        """))
        has_docs = result.scalar()

        if has_docs:
            result = conn.execute(text(f"""
                SELECT
                    document_type,
                    COUNT(*) as count
                FROM user_documents
                WHERE created_at >= '{cutoff_str}'
                GROUP BY document_type
                ORDER BY count DESC
            """))
            rows = result.fetchall()
            if rows:
                print("   Documents generated:")
                for doc_type, count in rows:
                    print(f"     - {doc_type}: {count}")
            else:
                print("   No documents generated in this period.")
        else:
            print("   [user_documents table not found]")

        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Check Brubru usage statistics')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyse (default: 7)')
    args = parser.parse_args()

    check_usage(days=args.days)


if __name__ == "__main__":
    main()
