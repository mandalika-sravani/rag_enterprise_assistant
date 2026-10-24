"""Users and the one access rule.

A user can read a chunk when BOTH are true:
  1. the chunk's department is "all", or one of the user's departments ("*" = every department)
  2. the chunk's access level is at or below the user's clearance (public < internal < restricted)
"""

import hmac
from pathlib import Path

import yaml
from pydantic import BaseModel

LEVELS = {"public": 0, "internal": 1, "restricted": 2}


class User(BaseModel):
    id: str
    name: str
    api_key: str
    departments: list[str] = []
    clearance: str = "public"
    is_admin: bool = False


def load_users(path: Path) -> dict[str, User]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {uid: User(id=uid, **info) for uid, info in data["users"].items()}


def find_user_by_key(users: dict[str, User], api_key: str | None) -> User | None:
    if not api_key:
        return None
    for user in users.values():
        if hmac.compare_digest(user.api_key, api_key):  # constant-time comparison
            return user
    return None


def can_read(user: User, metadata: dict) -> bool:
    """`metadata` is a LangChain Document's metadata (department + access level)."""
    access, department = metadata.get("access"), metadata.get("department")
    if access not in LEVELS or not department:
        return False  # unknown or missing classification: never shown
    department_ok = department == "all" or "*" in user.departments or department in user.departments
    return department_ok and LEVELS[access] <= LEVELS[user.clearance]
