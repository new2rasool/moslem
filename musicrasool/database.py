"""
MusicRasool - thread-safe SQLite layer.

All original tables are kept with identical semantics. A single
connection guarded by a lock is used (sqlite3 is not async-safe),
so every read/write goes through short, lock-protected calls.
"""
import sqlite3
import threading

import config

_lock = threading.RLock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.get_config().DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


# ----------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS gp(
    namegp TEXT,
    idgp BIGINT,
    linkgp TEXT,
    status INT
);
CREATE TABLE IF NOT EXISTS charge(
    idgp BIGINT,
    idadmin BIGINT,
    day INT,
    start BIGINT,
    end BIGINT,
    status INT,
    link TEXT,
    name TEXT
);
CREATE TABLE IF NOT EXISTS charge2(
    idgp BIGINT,
    idadmin BIGINT,
    day INT,
    start BIGINT,
    end BIGINT,
    status INT,
    link TEXT,
    name TEXT
);
CREATE TABLE IF NOT EXISTS information(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start TEXT,
    about TEXT,
    groupp TEXT,
    adminpv TEXT,
    payamresan TEXT
);
CREATE TABLE IF NOT EXISTS users(
    iduser BIGINT,
    lang TEXT DEFAULT 'fa'
);
CREATE TABLE IF NOT EXISTS videoadmins(
    idgp BIGINT,
    idadmin BIGINT,
    nameadmin TEXT
);
CREATE TABLE IF NOT EXISTS musicadmin(
    idgp BIGINT,
    idadmin BIGINT,
    nameadmin TEXT
);
CREATE TABLE IF NOT EXISTS sudo(
    idsudo BIGINT,
    namesudo TEXT
);
CREATE TABLE IF NOT EXISTS owner(
    idowner BIGINT,
    nameowner TEXT
);
CREATE TABLE IF NOT EXISTS alll(
    idsadmin BIGINT,
    namesadmin TEXT,
    status INT
);
CREATE TABLE IF NOT EXISTS channel(
    idchannel BIGINT,
    namechannel TEXT,
    invite TEXT,
    status INT
);
CREATE TABLE IF NOT EXISTS limmit(
    status INT,
    count INT
);
CREATE TABLE IF NOT EXISTS autoleft(
    status INT
);
CREATE TABLE IF NOT EXISTS creators(
    idgp BIGINT,
    creator BIGINT
);
CREATE TABLE IF NOT EXISTS playlist(
    idgp BIGINT,
    path TEXT,
    duration INT
);
CREATE TABLE IF NOT EXISTS money1(
    kos INT,
    nerkh1 INT,
    nerkh2 INT
);
CREATE TABLE IF NOT EXISTS paye(
    kos INT,
    nerkh INT
);
CREATE TABLE IF NOT EXISTS etebar(
    kos INT,
    start INT,
    end INT,
    status INT
);
CREATE TABLE IF NOT EXISTS chnl(
    idchnl INT,
    start INT,
    end INT,
    statuschnl INT,
    status INT
);
CREATE TABLE IF NOT EXISTS ejbar(
    idgp INT,
    idadmin INT
);
CREATE TABLE IF NOT EXISTS startcli(
    start TEXT
);
CREATE TABLE IF NOT EXISTS banlist(
    idgp BIGINT,
    ban BIGINT
);

-- ----------------------------------------------------------------------
-- Indexes for the columns the handlers actually filter on.
--
-- None of the tables above declare a key, so every lookup was a full table
-- scan. `CREATE INDEX IF NOT EXISTS` is idempotent and also applies to
-- databases created by older versions, so no migration is needed. Adding
-- real PRIMARY KEY / UNIQUE constraints instead would change insert
-- semantics, which is deliberately not done here.
-- ----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_iduser      ON users(iduser);
CREATE INDEX IF NOT EXISTS idx_gp_idgp           ON gp(idgp);
CREATE INDEX IF NOT EXISTS idx_charge_idgp       ON charge(idgp);
CREATE INDEX IF NOT EXISTS idx_charge_status     ON charge(status);
CREATE INDEX IF NOT EXISTS idx_charge2_idgp      ON charge2(idgp);
CREATE INDEX IF NOT EXISTS idx_charge2_status    ON charge2(status);
CREATE INDEX IF NOT EXISTS idx_musicadmin_pair   ON musicadmin(idgp, idadmin);
CREATE INDEX IF NOT EXISTS idx_videoadmins_pair  ON videoadmins(idgp, idadmin);
CREATE INDEX IF NOT EXISTS idx_creators_idgp     ON creators(idgp);
CREATE INDEX IF NOT EXISTS idx_playlist_idgp     ON playlist(idgp);
CREATE INDEX IF NOT EXISTS idx_ejbar_idgp        ON ejbar(idgp);
CREATE INDEX IF NOT EXISTS idx_banlist_ban       ON banlist(ban);
CREATE INDEX IF NOT EXISTS idx_sudo_idsudo       ON sudo(idsudo);
CREATE INDEX IF NOT EXISTS idx_owner_idowner     ON owner(idowner);
CREATE INDEX IF NOT EXISTS idx_alll_status       ON alll(status);
CREATE INDEX IF NOT EXISTS idx_money1_kos        ON money1(kos);
CREATE INDEX IF NOT EXISTS idx_paye_kos          ON paye(kos);
CREATE INDEX IF NOT EXISTS idx_etebar_kos        ON etebar(kos);
"""


def init_db():
    with _lock:
        db = _db()
        db.executescript(SCHEMA)
        db.commit()
        _seed_defaults(db)


def _seed_defaults(db):
    cur = db.cursor()
    # information row
    cur.execute("SELECT id FROM information WHERE id=1")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO information(id,start,about,groupp,adminpv,payamresan) "
            "VALUES(1,'START','ABOUT','+NFHJK4757FDSDF','bdchvjndchvj','dbgchjnebdh')"
        )
    # money1 : kos=1 -> owner rates, kos=2 -> sudo rates
    cur.execute("SELECT kos FROM money1")
    if cur.fetchall() == []:
        cur.executemany(
            "INSERT INTO money1(kos,nerkh1,nerkh2) VALUES(?,?,?)",
            [(1, 10000, 25000), (2, 15000, 30000)],
        )
    # startcli
    cur.execute("SELECT start FROM startcli")
    if cur.fetchall() == []:
        cur.execute("INSERT INTO startcli(start) VALUES(?)", ("Hi MENTION",))
    # paye
    cur.execute("SELECT kos FROM paye")
    if cur.fetchall() == []:
        cur.execute("INSERT INTO paye(kos,nerkh) VALUES(?,?)", (1, 50000))
    db.commit()


# ----------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------
def query(sql, params=()):
    """Return list of tuples for a SELECT."""
    with _lock:
        cur = _db().cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql, params=()):
    with _lock:
        cur = _db().cursor()
        cur.execute(sql, params)
        _db().commit()
        return cur.lastrowid


def executemany(sql, params_seq):
    with _lock:
        cur = _db().cursor()
        cur.executemany(sql, params_seq)
        _db().commit()


# ----------------------------------------------------------------------
# High level helpers (same semantics as the original bot)
# ----------------------------------------------------------------------
def idsudos():
    return [r[0] for r in query("SELECT idsudo FROM sudo")]


def idowner():
    return [r[0] for r in query("SELECT idowner FROM owner")]


def idmusic(chat_id):
    return [r[1] for r in query("SELECT idgp,idadmin,nameadmin FROM musicadmin WHERE idgp=?", (chat_id,))]


def idvideo(chat_id):
    return [r[1] for r in query("SELECT idgp,idadmin,nameadmin FROM videoadmins WHERE idgp=?", (chat_id,))]


def allvideo():
    return [r[0] for r in query("SELECT idsadmin FROM alll WHERE status=1")]


def allmusic():
    return [r[0] for r in query("SELECT idsadmin FROM alll WHERE status=0")]


def creators(chat_id):
    return [r[1] for r in query("SELECT idgp,creator FROM creators WHERE idgp=?", (chat_id,))]


def readusers():
    return [r[0] for r in query("SELECT iduser FROM users")]


def gpmusic():
    return [r[0] for r in query("SELECT idgp FROM charge")]


def gpvideo():
    return [r[0] for r in query("SELECT idgp FROM charge2")]


def insmusic():
    return [r[0] for r in query("SELECT idgp FROM gp WHERE status=0")]


def insvideo():
    return [r[0] for r in query("SELECT idgp FROM gp WHERE status=1")]


def moz(status: int):
    return [r[0] for r in query("SELECT idgp FROM charge WHERE status=?", (status,))]


def kir(status: int):
    return [r[0] for r in query("SELECT idgp FROM charge2 WHERE status=?", (status,))]


def info():
    rows = query("SELECT * FROM information WHERE id=1")
    if not rows:
        return None
    r = rows[0]
    return {
        "start": r[1],
        "about": r[2],
        "groupp": r[3],
        "adminpv": r[4],
        "payamresan": r[5],
    }


def channel():
    rows = query("SELECT * FROM channel")
    return rows


def get_lang(user_id: int) -> str:
    rows = query("SELECT lang FROM users WHERE iduser=?", (user_id,))
    if rows and rows[0][0] in ("fa", "en"):
        return rows[0][0]
    return config.get_config().DEFAULT_LANG


def set_lang(user_id: int, lang: str):
    execute("UPDATE users SET lang=? WHERE iduser=?", (lang, user_id))
    if query("SELECT iduser FROM users WHERE iduser=?", (user_id,)) == []:
        execute("INSERT INTO users(iduser,lang) VALUES(?,?)", (user_id, lang))


def add_user(user_id: int):
    if query("SELECT iduser FROM users WHERE iduser=?", (user_id,)) == []:
        execute("INSERT INTO users(iduser,lang) VALUES(?,?)", (user_id, config.get_config().DEFAULT_LANG))


def credit_status():
    """Return the bot's own credit row (etebar)."""
    rows = query("SELECT * FROM etebar")
    return rows[0] if rows else None
