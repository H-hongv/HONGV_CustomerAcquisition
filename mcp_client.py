"""Commercial-grade Model Context Protocol client integration.

The synchronous application owns one dedicated asyncio thread per MCP server.  A
single long-lived worker task owns the transport context for its whole lifetime;
this is important because the MCP SDK transports use task-bound async context
managers.  Calls are serialized per connection and different servers can still
run concurrently.
"""

import asyncio
import atexit
import json
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from logger import logger

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    MCP_AVAILABLE = True
except ImportError:
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. pip install mcp")

try:
    from mcp.client.sse import sse_client
except ImportError:
    sse_client = None

try:
    from mcp.client.streamable_http import streamablehttp_client
except ImportError:
    streamablehttp_client = None


_ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_VALID_CATEGORY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_VALID_MODES = frozenset(("free", "paid"))
_VALID_TRANSPORTS = frozenset(("stdio", "sse", "streamable_http"))


@dataclass
class MCPServerConfig:
    """Validated configuration for one MCP server."""

    name: str
    transport: str = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    category: str = "search"
    modes: List[str] = field(default_factory=lambda: ["free", "paid"])
    enabled: bool = True
    tool_name: str = ""
    argument_map: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "transport": self.transport,
            "command": self.command,
            "args": list(self.args),
            "env": dict(self.env),
            "url": self.url,
            "category": self.category,
            "modes": list(self.modes),
            "enabled": self.enabled,
            "tool_name": self.tool_name,
            "argument_map": dict(self.argument_map),
            "headers": dict(self.headers),
            "timeout_seconds": self.timeout_seconds,
        }

    @staticmethod
    def _string_dict(value: Any, field_name: str) -> Dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a JSON object")
        normalized = {}
        for key, item in value.items():
            key = str(key).strip()
            if not key:
                raise ValueError(f"{field_name} contains an empty key")
            if isinstance(item, (dict, list, tuple, set)):
                raise ValueError(f"{field_name}.{key} must be a scalar value")
            normalized[key] = "" if item is None else str(item)
        return normalized

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "1", "yes", "on"):
                return True
            if lowered in ("false", "0", "no", "off"):
                return False
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise ValueError("enabled must be a boolean")

    @classmethod
    def from_dict(cls, value: dict) -> "MCPServerConfig":
        if not isinstance(value, dict):
            raise ValueError("MCP server configuration must be a JSON object")

        raw_modes = value.get("modes", ["free", "paid"])
        if not isinstance(raw_modes, (list, tuple)) or not raw_modes:
            raise ValueError("modes must be a non-empty array containing free and/or paid")
        modes = []
        for raw_mode in raw_modes:
            mode = str(raw_mode).strip().lower()
            if mode not in _VALID_MODES:
                raise ValueError(f"Unsupported MCP mode: {raw_mode}")
            if mode not in modes:
                modes.append(mode)

        raw_args = value.get("args", [])
        if raw_args is None:
            raw_args = []
        if not isinstance(raw_args, (list, tuple)):
            raise ValueError("args must be a JSON array")

        raw_transport = str(value.get("transport", "stdio")).strip().lower()
        transport = "streamable_http" if raw_transport == "http" else raw_transport
        try:
            timeout_seconds = float(value.get("timeout_seconds", 30.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("timeout_seconds must be a number") from exc

        config = cls(
            name=str(value.get("name", "")).strip(),
            transport=transport,
            command=str(value.get("command", "") or "").strip(),
            args=[str(item) for item in raw_args],
            env=cls._string_dict(value.get("env", {}), "env"),
            url=str(value.get("url", "") or "").strip(),
            category=str(value.get("category", "search") or "search").strip().lower(),
            modes=modes,
            enabled=cls._boolean(value.get("enabled", True)),
            tool_name=str(value.get("tool_name", "") or "").strip(),
            argument_map=cls._string_dict(
                value.get("argument_map", {}), "argument_map"
            ),
            headers=cls._string_dict(value.get("headers", {}), "headers"),
            timeout_seconds=timeout_seconds,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.name:
            raise ValueError("MCP server name is required")
        if self.transport not in _VALID_TRANSPORTS:
            raise ValueError(f"Unsupported MCP transport: {self.transport}")
        if not self.category or not _VALID_CATEGORY.fullmatch(self.category):
            raise ValueError(f"Invalid MCP category: {self.category!r}")
        if not self.modes or any(mode not in _VALID_MODES for mode in self.modes):
            raise ValueError("modes must contain only free and/or paid")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.transport == "stdio" and not self.command:
            raise ValueError("command is required for stdio transport")
        if self.transport in ("sse", "streamable_http"):
            parsed = urlparse(self.url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(
                    f"A valid http(s) URL is required for {self.transport} transport"
                )
        for canonical, target in self.argument_map.items():
            if not canonical.strip() or not target.strip():
                raise ValueError("argument_map keys and values cannot be empty")


@dataclass
class MCPToolInfo:
    """Information about a tool discovered from an MCP server."""

    name: str
    description: str = ""
    server_name: str = ""
    category: str = "custom"
    input_schema: dict = field(default_factory=dict)


class MCPConnection:
    """Persistent, thread-safe connection to one MCP server."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._tools: List[MCPToolInfo] = []
        self._session = None
        self._connected = False
        self._error = ""
        self._loop = None
        self._thread = None
        self._exit_stack = None
        self._lock = threading.RLock()
        self._worker_task = None
        self._request_queue = None
        self._ready_event = None
        self._active_response = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def tools(self) -> List[MCPToolInfo]:
        with self._lock:
            return list(self._tools)

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def connect(self) -> bool:
        """Connect to the server and discover tools, keeping the session open."""
        if not MCP_AVAILABLE:
            self._error = "MCP SDK not installed"
            return False
        if not self.config.enabled:
            self._error = "Server disabled"
            return False
        try:
            self.config.validate()
        except ValueError as exc:
            self._error = str(exc)
            return False

        with self._lock:
            if self._connected and self._session is not None:
                return True
            try:
                self._ensure_event_loop()
                self._run(self._start_worker())
                return self._connected
            except Exception as exc:
                self._connected = False
                self._session = None
                self._error = str(exc)
                logger.warning(f"MCP connect failed [{self.config.name}]: {exc}")
                self.close()
                return False

    def _ensure_event_loop(self) -> None:
        if self._thread and self._thread.is_alive() and self._loop:
            return
        ready = threading.Event()

        def runner():
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            ready.set()
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

        self._thread = threading.Thread(
            target=runner, name=f"mcp-{self.config.name}", daemon=True
        )
        self._thread.start()
        if not ready.wait(timeout=5) or self._loop is None:
            raise RuntimeError("Failed to start MCP event loop")

    @staticmethod
    def _discard_coroutine(coroutine: Any) -> None:
        close = getattr(coroutine, "close", None)
        if callable(close):
            close()

    def _run(self, coroutine: Any, timeout: Optional[float] = None):
        loop = self._loop
        if loop is None or not loop.is_running():
            self._discard_coroutine(coroutine)
            raise RuntimeError("MCP event loop is not running")
        if threading.current_thread() is self._thread:
            self._discard_coroutine(coroutine)
            raise RuntimeError("Blocking MCP API cannot run on its own event-loop thread")
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        wait_seconds = max(timeout or self.config.timeout_seconds, 0.1)
        try:
            return future.result(timeout=wait_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"MCP operation timed out after {wait_seconds:g}s"
            ) from exc

    @staticmethod
    def _expand_env_references(
        values: Dict[str, str], strict: bool = False
    ) -> Dict[str, str]:
        missing = set()

        def expand(value: Any) -> str:
            if not isinstance(value, str):
                return str(value)

            def replace(match):
                name = match.group(1)
                resolved = os.getenv(name)
                if resolved is None:
                    missing.add(name)
                    return ""
                return resolved

            return _ENV_REFERENCE.sub(replace, value)

        expanded = {str(key): expand(value) for key, value in values.items()}
        if strict and missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Missing MCP environment variable(s): {names}")
        return expanded

    def _resolved_headers(self) -> Dict[str, str]:
        values = self._expand_env_references(self.config.headers, strict=True)
        return {key: value for key, value in values.items() if value}

    def _resolved_process_env(self) -> Optional[Dict[str, str]]:
        if not self.config.env:
            return None
        env = os.environ.copy()
        env.update(self._expand_env_references(self.config.env, strict=True))
        return env

    async def _start_worker(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._request_queue = asyncio.Queue()
        self._ready_event = asyncio.Event()
        self._worker_task = asyncio.create_task(
            self._session_worker(), name=f"mcp-session-{self.config.name}"
        )
        await self._ready_event.wait()
        if not self._connected:
            raise RuntimeError(self._error or "MCP connection failed")

    async def _session_worker(self) -> None:
        """Own the transport context and serialize calls for its whole lifetime."""
        try:
            try:
                await self._async_open()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._error = str(exc)
                self._connected = False
                self._session = None
            finally:
                if self._ready_event:
                    self._ready_event.set()

            if not self._connected:
                return

            while True:
                request = await self._request_queue.get()
                if request is None:
                    break
                tool_name, arguments, response = request
                self._active_response = response
                try:
                    value = await self._async_call_tool(tool_name, arguments)
                    if not response.done():
                        response.set_result(value)
                except asyncio.CancelledError:
                    if not response.done():
                        response.set_exception(RuntimeError("MCP connection closed"))
                    raise
                except Exception as exc:
                    if not response.done():
                        response.set_exception(exc)
                finally:
                    self._active_response = None
        finally:
            await self._fail_pending_requests("MCP connection closed")
            stack = self._exit_stack
            self._exit_stack = None
            if stack is not None:
                try:
                    await stack.aclose()
                except Exception as exc:
                    logger.debug(f"MCP transport close failed [{self.config.name}]: {exc}")
            self._connected = False
            self._session = None

    async def _fail_pending_requests(self, message: str) -> None:
        queue = self._request_queue
        if queue is None:
            return
        while True:
            try:
                request = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if request is None:
                continue
            response = request[2]
            if not response.done():
                response.set_exception(RuntimeError(message))

    async def _async_open(self) -> None:
        cfg = self.config
        self._exit_stack = AsyncExitStack()
        if cfg.transport == "stdio":
            params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args,
                env=self._resolved_process_env(),
            )
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
        elif cfg.transport == "sse":
            if sse_client is None:
                raise RuntimeError("Installed MCP SDK does not support SSE transport")
            read, write = await self._exit_stack.enter_async_context(
                sse_client(cfg.url, headers=self._resolved_headers())
            )
        else:
            if streamablehttp_client is None:
                raise RuntimeError(
                    "Installed MCP SDK does not support Streamable HTTP transport"
                )
            transport = await self._exit_stack.enter_async_context(
                streamablehttp_client(cfg.url, headers=self._resolved_headers())
            )
            read, write = transport[0], transport[1]

        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        result = await self._session.list_tools()
        self._tools = [
            MCPToolInfo(
                name=str(tool.name),
                description=getattr(tool, "description", "") or "",
                server_name=cfg.name,
                category=cfg.category,
                input_schema=getattr(tool, "inputSchema", {}) or {},
            )
            for tool in getattr(result, "tools", [])
            if getattr(tool, "name", None)
        ]
        self._connected = True
        self._error = ""

    def call_tool(self, tool_name: str, arguments: dict) -> Optional[str]:
        """Call one MCP tool. Errors are recorded and returned as ``None``."""
        if not tool_name or not isinstance(arguments, dict):
            self._error = "tool_name is required and arguments must be an object"
            return None
        with self._lock:
            if not self._connected and not self.connect():
                return None
            try:
                return self._run(self._enqueue_call(tool_name, arguments))
            except Exception as exc:
                self._error = str(exc)
                logger.warning(
                    f"MCP tool call failed [{self.config.name}/{tool_name}]: {exc}"
                )
                # Transport exceptions are not reliably distinguishable from
                # tool exceptions across MCP SDK versions. Reconnect on the next
                # call instead of reusing a session whose state is unknown.
                self.close()
                return None

    async def _enqueue_call(self, tool_name: str, arguments: dict) -> Optional[str]:
        if (
            not self._worker_task
            or self._worker_task.done()
            or self._request_queue is None
        ):
            raise RuntimeError("MCP session worker is not running")
        response = asyncio.get_running_loop().create_future()
        await self._request_queue.put((tool_name, arguments, response))
        return await response

    @staticmethod
    def _content_text(item: Any) -> str:
        text = getattr(item, "text", None)
        if text is not None:
            return str(text)
        resource = getattr(item, "resource", None)
        if resource is not None:
            resource_text = getattr(resource, "text", None)
            if resource_text is not None:
                return str(resource_text)
            blob = getattr(resource, "blob", None)
            if blob is not None:
                return str(blob)
        if isinstance(item, dict):
            for key in ("text", "content", "markdown"):
                if item.get(key) is not None:
                    return str(item[key])
        return ""

    async def _async_call_tool(self, tool_name: str, arguments: dict) -> Optional[str]:
        if self._session is None:
            raise RuntimeError("MCP session is not initialized")
        result = await self._session.call_tool(tool_name, arguments)
        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        chunks = [
            text
            for text in (
                self._content_text(item)
                for item in (getattr(result, "content", None) or [])
            )
            if text
        ]
        is_error = bool(
            getattr(result, "isError", getattr(result, "is_error", False))
        )
        if is_error:
            raise RuntimeError("\n".join(chunks) or "MCP tool returned an error")
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False, default=str)
        return "\n".join(chunks) if chunks else None

    def close(self) -> None:
        """Close the worker, transport, loop and thread without leaking tasks."""
        with self._lock:
            loop = self._loop
            thread = self._thread
            if loop and loop.is_running() and threading.current_thread() is not thread:
                shutdown_timeout = min(max(self.config.timeout_seconds, 0.25), 5.0)
                if self._worker_task and not self._worker_task.done():
                    try:
                        self._run(
                            self._stop_worker(shutdown_timeout),
                            timeout=shutdown_timeout + 1.0,
                        )
                    except Exception as exc:
                        logger.debug(f"MCP close failed [{self.config.name}]: {exc}")
                        task = self._worker_task
                        if task and not task.done():
                            loop.call_soon_threadsafe(task.cancel)
                loop.call_soon_threadsafe(loop.stop)
                if thread and thread.is_alive():
                    thread.join(timeout=shutdown_timeout + 1.0)
            elif loop and loop.is_running():
                task = self._worker_task
                if task and not task.done():
                    task.cancel()
                loop.stop()

            self._connected = False
            self._session = None
            self._tools = []
            self._exit_stack = None
            self._worker_task = None
            self._request_queue = None
            self._ready_event = None
            self._active_response = None
            self._loop = None
            self._thread = None

    async def _stop_worker(self, timeout: float) -> None:
        task = self._worker_task
        if task is None:
            return
        if not task.done() and self._request_queue is not None:
            await self._request_queue.put(None)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


class MCPManager:
    """Mode-isolated manager for discovery and category-based tool routing."""

    def __init__(self):
        self._servers: Dict[str, MCPConnection] = {}
        self._tools_cache: Dict[str, List[MCPToolInfo]] = {}
        self._config_errors: List[dict] = []
        self._initialized = False
        self._mode = "free"
        self._generation = 0
        self._lock = threading.RLock()

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def configuration_errors(self) -> List[dict]:
        with self._lock:
            return [dict(item) for item in self._config_errors]

    def load_configs(self, configs: List[dict], mode: str = "free") -> None:
        """Validate and atomically load only servers allowed in ``mode``."""
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in _VALID_MODES:
            raise ValueError("MCP mode must be 'free' or 'paid'")
        if configs is None:
            configs = []
        if not isinstance(configs, (list, tuple)):
            raise ValueError("mcp_servers must be a JSON array")

        selected: Dict[str, MCPConnection] = {}
        errors = []
        for index, raw_config in enumerate(configs):
            try:
                config = MCPServerConfig.from_dict(raw_config)
            except (TypeError, ValueError) as exc:
                raw_name = raw_config.get("name") if isinstance(raw_config, dict) else None
                name = str(raw_name or f"config[{index}]")
                errors.append({"name": name, "error": str(exc)})
                logger.warning(f"Ignoring invalid MCP server [{name}]: {exc}")
                continue
            if not config.enabled or normalized_mode not in config.modes:
                continue
            if config.name in selected:
                logger.warning(
                    f"Duplicate MCP server [{config.name}] for mode={normalized_mode}; "
                    "the last configuration wins"
                )
            selected[config.name] = MCPConnection(config)

        with self._lock:
            old_connections = list(self._servers.values())
            self._servers = selected
            self._tools_cache = {}
            self._config_errors = errors
            self._mode = normalized_mode
            self._initialized = True
            self._generation += 1

        for connection in old_connections:
            connection.close()
        logger.info(
            f"MCP Manager loaded {len(selected)} servers for mode={normalized_mode}"
        )

    def discover_all(self) -> Dict[str, List[MCPToolInfo]]:
        """Discover servers concurrently and commit only to the active generation."""
        with self._lock:
            generation = self._generation
            servers = list(self._servers.items())
        if not servers:
            return {}

        discovered: Dict[str, List[MCPToolInfo]] = {}

        def connect_one(item: Tuple[str, MCPConnection]):
            name, connection = item
            with self._lock:
                if generation != self._generation:
                    return name, connection, False
            return name, connection, connection.connect()

        with ThreadPoolExecutor(max_workers=min(len(servers), 8)) as executor:
            futures = [executor.submit(connect_one, item) for item in servers]
            for future in as_completed(futures):
                name, connection, connected = future.result()
                if connected:
                    tools = connection.tools
                    discovered[name] = tools
                    logger.info(f"MCP [{name}]: {len(tools)} tools discovered")
                    explicit = connection.config.tool_name
                    if explicit and not any(tool.name == explicit for tool in tools):
                        logger.warning(
                            f"MCP [{name}]: configured tool_name '{explicit}' was not found"
                        )
                else:
                    discovered[name] = []
                    logger.warning(
                        f"MCP [{name}]: connection failed - {connection.error}"
                    )

        ordered = {name: discovered.get(name, []) for name, _ in servers}
        with self._lock:
            if generation != self._generation:
                logger.info("Discarding stale MCP discovery after mode/config change")
                return {}
            self._tools_cache = ordered
        return {name: list(tools) for name, tools in ordered.items()}

    @staticmethod
    def _tool_arguments(
        tool: MCPToolInfo,
        canonical: Dict[str, Any],
        mapping: Dict[str, str],
    ) -> Dict[str, Any]:
        """Map stable pipeline arguments to a custom MCP input schema."""
        schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        aliases = {
            "query": ("query", "q", "search_query", "text", "keyword"),
            "max_results": (
                "max_results",
                "limit",
                "count",
                "num_results",
                "maxResults",
            ),
            "url": ("url", "uri", "target_url", "website", "targetUrl"),
        }
        result = {}
        for canonical_name, value in canonical.items():
            target = mapping.get(canonical_name)
            if not target:
                target = next(
                    (
                        name
                        for name in aliases.get(canonical_name, (canonical_name,))
                        if name in properties
                    ),
                    None,
                )
            if not target:
                # A result limit is optional and strict schemas often reject unknown
                # fields. Query and URL remain required canonical fallbacks.
                if canonical_name == "max_results" and properties:
                    continue
                target = canonical_name
            result[target] = value
        return result

    def _category_snapshot(
        self, category: str
    ) -> Tuple[int, List[Tuple[MCPConnection, MCPToolInfo]]]:
        with self._lock:
            generation = self._generation
            pairs = []
            for server_name, tool_list in self._tools_cache.items():
                connection = self._servers.get(server_name)
                if not connection or connection.config.category != category:
                    continue
                explicit = connection.config.tool_name
                for tool in tool_list:
                    if tool.category != category:
                        continue
                    if explicit and tool.name != explicit:
                        continue
                    pairs.append((connection, tool))
            return generation, pairs

    def get_tools_by_category(self, category: str) -> List[MCPToolInfo]:
        """Return a snapshot of callable tools in a category."""
        _, pairs = self._category_snapshot(str(category).strip().lower())
        return [tool for _, tool in pairs]

    def has_tools(self, category: str) -> bool:
        """Whether the active mode has at least one callable discovered tool."""
        _, pairs = self._category_snapshot(str(category).strip().lower())
        return bool(pairs)

    def call_tool(self, tool_name: str, arguments: dict) -> Optional[str]:
        """Call a discovered MCP tool by name across active servers (best-effort)."""
        name = str(tool_name or "").strip()
        if not name:
            return None
        try:
            with self._lock:
                generation = self._generation
                pairs = []
                for server_name, tool_list in self._tools_cache.items():
                    connection = self._servers.get(server_name)
                    if not connection:
                        continue
                    if getattr(connection.config, "tool_name", ""):
                        if connection.config.tool_name != name:
                            continue  # server pinned to a specific tool
                    for tool in tool_list:
                        if tool.name == name:
                            pairs.append((connection, tool))
            for connection, tool in pairs:
                if generation != self._generation:
                    return None  # config reloaded while calling
                try:
                    mapped = self._tool_arguments(
                        tool, dict(arguments or {}), connection.config.argument_map
                    )
                    result = connection.call_tool(tool.name, mapped)
                    if result is not None:
                        if generation != self._generation:
                            return None  # config reloaded while calling
                        return result
                except Exception as exc:
                    logger.warning(f"MCP call_tool {tool_name} on {connection.config.name} failed: {exc}")
            return None
        except Exception as exc:
            logger.warning(f"MCP call_tool {tool_name} failed: {exc}")
        return None

    @staticmethod
    def _decode_response(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return raw

    @classmethod
    def _search_items(cls, value: Any, depth: int = 0) -> List[dict]:
        if depth > 3:
            return []
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.extend(cls._search_items(item, depth + 1))
            return items
        if not isinstance(value, dict):
            return []
        if any(value.get(key) for key in ("url", "link", "href", "website")):
            return [dict(value)]
        for key in (
            "results",
            "items",
            "data",
            "organic_results",
            "web_results",
            "matches",
            "documents",
        ):
            nested = value.get(key)
            if isinstance(nested, (list, dict)):
                items = cls._search_items(nested, depth + 1)
                if items:
                    return items
        return []

    def call_search(self, query: str, max_results: int = 10) -> List[dict]:
        """Call all active search MCP tools concurrently and normalize results."""
        query = str(query or "").strip()
        if not query:
            return []
        try:
            limit = max(1, min(int(max_results), 100))
        except (TypeError, ValueError):
            limit = 10
        generation, pairs = self._category_snapshot("search")
        if not pairs:
            return []

        def call_one(pair):
            connection, tool = pair
            with self._lock:
                if generation != self._generation:
                    return []
            arguments = self._tool_arguments(
                tool,
                {"query": query, "max_results": limit},
                connection.config.argument_map,
            )
            raw = connection.call_tool(tool.name, arguments)
            if not raw:
                return []
            normalized = []
            for item in self._search_items(self._decode_response(raw)):
                item = dict(item)
                item.setdefault("source", tool.server_name)
                item.setdefault("mcp_tool", tool.name)
                normalized.append(item)
            return normalized

        batches = {}
        with ThreadPoolExecutor(max_workers=min(len(pairs), 8)) as executor:
            futures = {
                executor.submit(call_one, pair): index
                for index, pair in enumerate(pairs)
            }
            for future in as_completed(futures):
                try:
                    batches[futures[future]] = future.result()
                except Exception as exc:
                    logger.warning(f"MCP search tool failed: {exc}")

        with self._lock:
            if generation != self._generation:
                logger.info("Discarding stale MCP search results after mode change")
                return []
        results = []
        for index in range(len(pairs)):
            results.extend(batches.get(index, []))
        return results

    @classmethod
    def _extract_crawl_content(cls, value: Any, depth: int = 0) -> str:
        if depth > 4 or value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = [cls._extract_crawl_content(item, depth + 1) for item in value]
            return "\n\n".join(part for part in parts if part)
        if not isinstance(value, dict):
            return ""
        for key in ("content", "markdown", "text", "html", "body"):
            if key in value:
                content = cls._extract_crawl_content(value.get(key), depth + 1)
                if content:
                    return content
        for key in ("result", "data", "document", "page"):
            nested = value.get(key)
            if isinstance(nested, (dict, list, str)):
                content = cls._extract_crawl_content(nested, depth + 1)
                if content:
                    return content
        return ""

    @classmethod
    def _crawl_payload(
        cls, raw: str, server_name: str, tool_name: str
    ) -> Optional[dict]:
        decoded = cls._decode_response(raw)
        content = cls._extract_crawl_content(decoded)
        if not content:
            return None
        metadata = {"mcp_server": server_name, "mcp_tool": tool_name}
        if isinstance(decoded, dict):
            source_metadata = decoded.get("metadata")
            if isinstance(source_metadata, dict):
                metadata.update(source_metadata)
            for key in ("title", "description", "language", "emails", "phones"):
                if key in decoded and key not in metadata:
                    metadata[key] = decoded[key]
        return {
            "content": content,
            "server": server_name,
            "tool": tool_name,
            "metadata": metadata,
        }

    def call_crawl(self, url: str, include_metadata: bool = False):
        """Call crawl tools in order; return the first usable normalized response."""
        url = str(url or "").strip()
        if not url:
            return None
        generation, pairs = self._category_snapshot("crawl")
        for connection, tool in pairs:
            with self._lock:
                if generation != self._generation:
                    logger.info("Stopping stale MCP crawl fallback after mode change")
                    return None
            arguments = self._tool_arguments(
                tool, {"url": url}, connection.config.argument_map
            )
            raw = connection.call_tool(tool.name, arguments)
            if not raw:
                continue
            payload = self._crawl_payload(raw, tool.server_name, tool.name)
            if not payload:
                continue
            with self._lock:
                if generation != self._generation:
                    logger.info("Discarding stale MCP crawl result after mode change")
                    return None
            return payload if include_metadata else payload["content"]
        return None

    def close(self) -> None:
        """Atomically detach and close all active mode-specific connections."""
        with self._lock:
            connections = list(self._servers.values())
            self._servers = {}
            self._tools_cache = {}
            self._config_errors = []
            self._initialized = False
            self._generation += 1
        for connection in connections:
            connection.close()

    def get_status(self) -> List[dict]:
        """Return immutable status records for configured and invalid servers."""
        with self._lock:
            mode = self._mode
            servers = list(self._servers.items())
            errors = [dict(item) for item in self._config_errors]
        status = [
            {
                "name": name,
                "connected": connection.is_connected,
                "tools_count": len(connection.tools),
                "category": connection.config.category,
                "transport": connection.config.transport,
                "mode": mode,
                "error": connection.error if not connection.is_connected else "",
                "enabled": connection.config.enabled,
                "configuration_error": False,
            }
            for name, connection in servers
        ]
        for error in errors:
            status.append(
                {
                    "name": error["name"],
                    "connected": False,
                    "tools_count": 0,
                    "category": "",
                    "transport": "",
                    "mode": mode,
                    "error": error["error"],
                    "enabled": False,
                    "configuration_error": True,
                }
            )
        return status


mcp_manager = MCPManager()
atexit.register(mcp_manager.close)
