from __future__ import annotations

import platform

import httpx
from loguru import logger

from bridge.config import BridgeConfig

MAX_RETRIES = 3
RETRY_DELAY = 2.0


def _normalize_os() -> str:
    """Map Python's platform.system() to protocol vocabulary."""
    sysname = platform.system()
    mapping = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
    return mapping.get(sysname, sysname.lower())


class ApiClient:
    """Cloud API client with retry logic and client identity headers."""

    def __init__(self, config: BridgeConfig):
        self.base_url = config.cloud.api_url.rstrip("/")
        self.headers = {
            "X-API-Key": config.cloud.api_key,
            "X-Client-Platform": "bridge",
            "X-Client-OS": _normalize_os(),
        }
        # Append version if available
        version = getattr(config, "_version", "")
        if version:
            self.headers["X-Client-Version"] = version
        self.machine_config = config.machine
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            headers=self.headers,
        )
        self.machine_uuid: str | None = None

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict | None:
        """Make HTTP request with retry."""
        url = f"{self.base_url}{path}"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP {e.response.status_code} for {method} {path}: {e.response.text}")
                return None
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                logger.warning(f"Network error (attempt {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"Unexpected error for {method} {path}: {e}")
                return None
        logger.error(f"All {MAX_RETRIES} retries failed for {method} {path}")
        return None

    async def register_machine(self) -> bool:
        """Register this machine with the cloud."""
        payload = {
            "machine_id": self.machine_config.machine_id,
            "machine_name": self.machine_config.machine_name,
            "agent_type": self.machine_config.agent_type,
            "agent_capability": self.machine_config.agent_capability,
        }
        if self.machine_config.project_id:
            payload["project_id"] = self.machine_config.project_id

        result = await self._request("POST", "/machines", json=payload)
        if result and result.get("success"):
            self.machine_uuid = result["data"]["id"]
            logger.info(f"Registered machine: {self.machine_config.machine_id} (uuid={self.machine_uuid})")
            return True
        logger.error("Failed to register machine")
        return False

    async def poll_tasks(self, project_id: str | None = None) -> list[dict]:
        """Poll for pending tasks for this machine's project."""
        if not self.machine_uuid:
            logger.warning("Machine not registered, skipping poll")
            return []

        path = f"/machines/{self.machine_uuid}/poll"
        # project_id parameter overrides config; None uses config value
        effective_project_id = project_id if project_id is not None else self.machine_config.project_id
        if effective_project_id:
            path = f"{path}?project_id={effective_project_id}"

        result = await self._request("GET", path)
        if result and "tasks" in result:
            tasks = result["tasks"]
            if tasks:
                logger.info(f"Polled {len(tasks)} task(s)")
            return tasks
        return []

    async def update_task_status(self, task_id: str, status: str) -> bool:
        """Update task status."""
        result = await self._request("PUT", f"/tasks/{task_id}", json={"status": status})
        return bool(result and result.get("success"))

    async def submit_result(self, task_id: str, result_data: dict) -> bool:
        """Submit execution result (optionally includes session_id and work_dir)."""
        result = await self._request("POST", f"/tasks/{task_id}/result", json=result_data)
        return bool(result and result.get("success"))

    async def pin_task_session(self, task_id: str, session_id: str | None = None, work_dir: str | None = None) -> bool:
        """Pin session_id and work_dir mid-run for crash recovery (Multica-inspired)."""
        payload = {}
        if session_id is not None:
            payload["session_id"] = session_id
        if work_dir is not None:
            payload["work_dir"] = work_dir
        if not payload:
            return True
        result = await self._request("PUT", f"/tasks/{task_id}/pin", json=payload)
        return bool(result and result.get("success"))

    async def get_task(self, task_id: str) -> dict | None:
        """Get task details by ID."""
        result = await self._request("GET", f"/tasks/{task_id}")
        return result.get("data") if result else None

    async def send_reminder(self, task_id: str) -> bool:
        """Trigger reminder for manual_only tasks."""
        result = await self._request("POST", f"/tasks/{task_id}/remind")
        return bool(result and result.get("success"))

    async def submit_progress(self, task_id: str, stdout_delta: str, stderr_delta: str) -> bool:
        """Submit incremental stdout/stderr during task execution."""
        payload: dict[str, str | int | None] = {}
        if stdout_delta:
            payload["stdout_delta"] = stdout_delta
        if stderr_delta:
            payload["stderr_delta"] = stderr_delta
        if not payload:
            return True
        result = await self._request("POST", f"/tasks/{task_id}/progress", json=payload)
        return bool(result and result.get("success"))

    async def update_agent_status(self, agent_status: str) -> bool:
        """Update agent status (idle/busy/offline)."""
        if not self.machine_uuid:
            return False
        result = await self._request("PATCH", f"/machines/{self.machine_uuid}", json={"agent_status": agent_status})
        return bool(result and result.get("success"))
