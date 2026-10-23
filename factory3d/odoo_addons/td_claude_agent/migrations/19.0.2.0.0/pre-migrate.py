def migrate(cr, version):
    """v2: агент = (власник, роль): знімаємо стару унікальність за власником."""
    cr.execute("ALTER TABLE td_claude_agent DROP CONSTRAINT IF EXISTS td_claude_agent_owner_uniq")
