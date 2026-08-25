import sqlite3
DB = r"E:\crawlio.io/backend/dev.db"
c = sqlite3.connect(DB); cur = c.cursor()

# 1. Fix direction: outbound for ai/user replies
cur.execute("""UPDATE email_conversation_messages
               SET direction='outbound'
               WHERE direction='inbound' AND sender_type IN ('ai','user')""")
print("direction rows updated:", cur.rowcount)

# 2. Canonical = aa454866; merge three dupes
keep = 'aa454866-878a-4563-af27-27fc124881cc'
dups = ['ca80ed35-1e32-42c5-af3d-c498348fcfc0',
        '5bf83e3f-c58c-4efb-b65a-58faa94cf7c5',
        'cf2bcfa1-8e78-41ea-a235-da917b6ea303']
cur.execute("SELECT COUNT(*) FROM email_conversation_messages WHERE conversation_id IN (%s)" % ','.join('?'*len(dups)), dups)
print("messages repainted to canonical convo:", cur.fetchone()[0])
cur.execute("UPDATE email_conversation_messages SET conversation_id=? WHERE conversation_id IN (%s)" % ','.join('?'*len(dups)), [keep]+dups)
cur.execute("DELETE FROM email_conversations WHERE id IN (%s)" % ','.join('?'*len(dups)), dups)
print("dup conversations deleted:", cur.rowcount)

# 3. Remove self-loop conversation (own email as customer)
sl = ['0c76339f-95f9-44f8-808a-f75f03646897']
cur.execute("DELETE FROM email_conversation_messages WHERE conversation_id IN (%s)" % ','.join('?'*len(sl)), sl)
cur.execute("DELETE FROM email_conversations WHERE id IN (%s)" % ','.join('?'*len(sl)), sl)
print("self-loop conversation deleted:", cur.rowcount)

# 4. Deduplicate email_accounts -> keep 2063, delete 258c
cur.execute("DELETE FROM email_accounts WHERE id='258c17cb-4464-4021-ac98-d913538ced7a'")
print("duplicate email_account deleted:", cur.rowcount)

# 5. Turn on ai agent for test
cur.execute("UPDATE email_conversations SET ai_agent_active=1 WHERE customer_email='awahaj960@gmail.com'")
print("awahaj convo ai_agent_active=1:", cur.rowcount)

c.commit(); c.close()
print("DONE")
