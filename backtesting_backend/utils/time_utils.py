from __future__ import annotations
from datetime import datetime, timezone
import re


def to_millis(dt_str: str) -> int:
	"""Convert an ISO datetime string to milliseconds since epoch (UTC)."""
	# parse using datetime.fromisoformat when possible
	try:
		dt = datetime.fromisoformat(dt_str)
		if dt.tzinfo is None:
			dt = dt.replace(tzinfo=timezone.utc)
		return int(dt.timestamp() * 1000)
	except Exception:
		# fallback: try parsing as %Y-%m-%d %H:%M:%S
		dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
		dt = dt.replace(tzinfo=timezone.utc)
		return int(dt.timestamp() * 1000)


def from_millis(ms: int) -> str:
	"""Convert milliseconds since epoch to ISO-format UTC string."""
	dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
	return dt.isoformat()


_interval_pattern = re.compile(r"^(\d+)([mhdwM])$")


def interval_to_millis(interval: str) -> int:
	"""Convert interval string like '1m','1h','1d' to milliseconds."""
	m = _interval_pattern.match(interval)
	if not m:
		raise ValueError(f"Invalid interval format: {interval}")
	qty = int(m.group(1))
	unit = m.group(2)
	if unit == "m":
		return qty * 60 * 1000
	if unit == "h":
		return qty * 60 * 60 * 1000
	if unit == "d":
		return qty * 24 * 60 * 60 * 1000
	if unit == "w":
		return qty * 7 * 24 * 60 * 60 * 1000
	if unit == "M":
		return qty * 30 * 24 * 60 * 60 * 1000
	raise ValueError(f"Unsupported interval unit: {unit}")
