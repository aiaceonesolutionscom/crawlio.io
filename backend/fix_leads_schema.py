import sqlite3
DB=r"E:\crawlio.io/backend/dev.db"
c=sqlite3.connect(DB); cur=c.cursor()
cols=[r[1] for r in cur.execute("PRAGMA table_info(leads)")]
add=[]
for col,typ in [("lat","REAL"),("lon","REAL")]:
    if col not in cols:
        cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {typ} NULL")
        add.append(col)
print("added cols:", add)
if "updated_at" in cols:
    cur.execute("CREATE INDEX IF NOT EXISTS ix_leads_workspace_id ON leads(workspace_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_leads_unsubscribed_at ON leads(unsubscribed_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_leads_outreach_sent_at ON leads(outreach_sent_at)")
c.commit(); c.close(); print("DONE")
