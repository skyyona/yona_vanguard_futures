"""Engine settings store using sqlite3.

Provides simple CRUD helpers for per-engine configuration such as enable/disable
flags and per-engine risk overrides.
"""

from typing import Optional, Dict, Any, List
import time

from engine_backend.db.manager import get_conn


def _now_utc() -> str:
	return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def upsert_engine_settings(
	engine_name: str,
	enabled: Optional[bool] = None,
	max_position_usdt: Optional[float] = None,
	max_leverage: Optional[int] = None,
	cooldown_sec: Optional[float] = None,
	note: Optional[str] = None,
	db_path: Optional[str] = None,
) -> None:
	"""Insert or update engine settings.

	If a row for the engine does not exist, it will be created with defaults
	and provided overrides. If it exists, only non-None fields are updated.
	"""

	conn = get_conn(db_path)
	cur = conn.cursor()

	cur.execute(
		"SELECT id, enabled, max_position_usdt, max_leverage, cooldown_sec, note FROM engine_settings WHERE engine_name = ?",
		(engine_name,),
	)
	row = cur.fetchone()

	now = _now_utc()

	if row is None:
		# insert new row
		cur.execute(
			"""
			INSERT INTO engine_settings (
				engine_name, enabled, max_position_usdt, max_leverage, cooldown_sec, note, updated_at_utc
			) VALUES (?, ?, ?, ?, ?, ?, ?)
			""",
			(
				engine_name,
				1 if (enabled is None or enabled) else 0,
				max_position_usdt,
				max_leverage,
				cooldown_sec,
				note,
				now,
			),
		)
	else:
		# update existing row with provided overrides
		current = dict(row)
		new_enabled = current["enabled"] if enabled is None else (1 if enabled else 0)
		new_max_pos = current["max_position_usdt"] if max_position_usdt is None else max_position_usdt
		new_max_lev = current["max_leverage"] if max_leverage is None else max_leverage
		new_cooldown = current["cooldown_sec"] if cooldown_sec is None else cooldown_sec
		new_note = current["note"] if note is None else note

		cur.execute(
			"""
			UPDATE engine_settings
			SET enabled = ?, max_position_usdt = ?, max_leverage = ?, cooldown_sec = ?, note = ?, updated_at_utc = ?
			WHERE engine_name = ?
			""",
			(
				new_enabled,
				new_max_pos,
				new_max_lev,
				new_cooldown,
				new_note,
				now,
				engine_name,
			),
		)

	conn.commit()
	conn.close()


def get_engine_settings(engine_name: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
	conn = get_conn(db_path)
	cur = conn.cursor()
	cur.execute(
		"SELECT engine_name, enabled, max_position_usdt, max_leverage, cooldown_sec, note, updated_at_utc FROM engine_settings WHERE engine_name = ?",
		(engine_name,),
	)
	row = cur.fetchone()
	conn.close()
	if not row:
		return None
	d = dict(row)
	d["enabled"] = bool(d.get("enabled", 0))
	return d


def list_engine_settings(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
	conn = get_conn(db_path)
	cur = conn.cursor()
	cur.execute(
		"SELECT engine_name, enabled, max_position_usdt, max_leverage, cooldown_sec, note, updated_at_utc FROM engine_settings ORDER BY engine_name"
	)
	rows = cur.fetchall()
	conn.close()
	out: List[Dict[str, Any]] = []
	for r in rows:
		d = dict(r)
		d["enabled"] = bool(d.get("enabled", 0))
		out.append(d)
	return out
