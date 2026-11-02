"""
Active-Window Context Profiler for Qale.
Captures foreground window and executable BEFORE HUD appears to prevent focus theft.
Selects context profiles (TypeScript, Python, Terminal, Prose) and caches
TechCorrector instances per profile for zero-overhead inference.
"""
import ctypes
import os
import re
from ctypes import wintypes
from typing import Dict, Any, List, Optional, Tuple

u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def active_window() -> Tuple[str, str, int]:
    """Captures foreground window executable, title, and HWND."""
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        return "", "", 0
    n = u32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, title, n + 1)
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    exe = ""
    h = k32.OpenProcess(0x1000, False, pid.value)
    if h:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            exe = os.path.basename(buf.value).lower()
        k32.CloseHandle(h)
    return exe, title.value, hwnd


DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "ts": {
        "prompt": "Developing scalable software systems, modules, database transactions, inventory, sales, customer orders, invoices, audit trails, and data consistency. Full-stack TypeScript, React, Next.js, NestJS, Zustand, Zod, TanStack Query, PostgreSQL, Node.js, RESTful APIs, JWT authentication, Claude.",
        "lex": ["useState", "useEffect", "interface", "props", "Tailwind CSS", "TanStack Query", "Zustand", "Zod", "Next.js", "NestJS", "PostgreSQL", "RESTful", "Node.js", "Claude", "scalable", "audit trail", "database transaction", "consistency", "inconsistent", "rollback", "inventory", "invoices"]
    },
    "py": {
        "prompt": "Developing Python modules in main.py with FastAPI, pytest, NumPy, PostgreSQL, Docker, RESTful API, Claude AI, pip install, run.bat, setup.bat.",
        "lex": ["FastAPI", "pytest", "numpy", "pip", "Python", "import", "def", "class", "PostgreSQL", "Docker", "RESTful", "Claude"]
    },
    "systems": {
        "prompt": "Systems programming in Rust, Go, C++, C#, Java. Structs, traits, goroutines, concurrency, mutexes, memory, cargo, pointers, async await, microservices.",
        "lex": ["Rust", "Golang", "Cargo", "struct", "trait", "impl", "fn", "pub", "async", "await", "goroutine", "mutex", "channel", "pointer", "C++", "C#", "Java", "Kotlin"]
    },
    "devops": {
        "prompt": "DevOps infrastructure, containers, cloud, databases. Docker, Kubernetes, Terraform, PostgreSQL, Prisma, SQL, Helm, NGINX, GitHub Actions, AWS, Azure, GCP.",
        "lex": ["Docker", "Kubernetes", "kubectl", "Terraform", "PostgreSQL", "Prisma", "SQL", "NGINX", "Redis", "Helm", "CI/CD", "GitHub Actions", "AWS", "GCP", "Azure"]
    },
    "term": {
        "prompt": "Running terminal commands: git status, git commit, npm run dev, pip install, docker compose, run.bat, setup.bat, python main.py.",
        "lex": ["git", "npm", "docker", "pip", "status", "commit", "push", "pull", "checkout", "run.bat", "setup.bat"]
    },
    "prose": {
        "prompt": "Software engineering, scalable systems, inventory, sales, customer orders, invoices, database transactions, data consistency, audit trails, and technical documentation.",
        "lex": ["scalable", "inventory", "sales", "invoices", "database transactions", "data consistency", "audit trail", "rollback", "inconsistent"]
    }
}

DEFAULT_BASE_LEXICON = [
    "Tailwind CSS", "RESTful", "PostgreSQL", "TypeScript",
    "JavaScript", "Next.js", "Zustand", "Zod", "React", "Node.js", "NestJS",
    "MongoDB", "Express", "Claude", "FastAPI", "pytest", "Ethiopian birr", "Ethiopian",
    "Vite", "React Hook Form",
    "scalable", "audit trail", "database transaction", "consistency", "inconsistent", "rollback"
]


def pick_profile(exe: str, title: str) -> str:
    """Selects the context profile based on process image name and window title."""
    exe = exe.lower()
    t = title.lower()

    # Terminal & CLI shells
    if exe in ("windowsterminal.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "wt.exe", "bash.exe", "wsl.exe", "mintty.exe", "git-bash.exe", "alacritty.exe", "hyper.exe"):
        return "term"

    # Code editors & IDEs
    if exe in ("code.exe", "cursor.exe", "devenv.exe", "notepad.exe", "notepad++.exe", "sublime_text.exe", "pycharm64.exe", "idea64.exe", "webstorm64.exe", "clion64.exe", "rider64.exe", "rustrover64.exe", "zed.exe"):
        if re.search(r"\.(tsx?|jsx?|vue|svelte|astro|css|scss|html)\b", t):
            return "ts"
        if re.search(r"\.(py|ipynb)\b", t):
            return "py"
        if re.search(r"\.(rs|go|cpp|c|h|cs|java|kt)\b", t):
            return "systems"
        if re.search(r"\.(sql|prisma|ya?ml|toml|json|dockerfile|env|sh|bat|ps1)\b", t) or "dockerfile" in t:
            return "devops"
        if re.search(r"\.(md|txt|log|rst)\b", t) or exe in ("notepad.exe", "notepad++.exe"):
            return "prose"
        return "ts"

    # Chat, Docs & Browsers
    if exe in ("slack.exe", "discord.exe", "teams.exe", "whatsapp.exe", "telegram.exe", "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "notion.exe", "obsidian.exe"):
        return "prose"

    return "prose"


class ContextProfileManager:
    """Manages context profiles and caches a TechCorrector instance per profile."""
    def __init__(self, config_manager=None):
        self.config = config_manager
        self.correctors: Dict[str, Any] = {}
        self.profiles: Dict[str, Any] = {}
        self.base_lexicon: List[str] = []
        self.learned: Dict[str, str] = {}
        self._reload_cache()

    def _reload_cache(self):
        from core.tech_corrector import TechCorrector

        if self.config:
            self.profiles = self.config.get("context_profiles", "profiles", default=DEFAULT_PROFILES)
            self.base_lexicon = self.config.get("ai", "base_lexicon", default=DEFAULT_BASE_LEXICON)
            self.learned = self.config.get_sound_alikes()
        else:
            self.profiles = DEFAULT_PROFILES
            self.base_lexicon = DEFAULT_BASE_LEXICON
            self.learned = {}

        # Cache one TechCorrector per profile
        self.correctors = {}
        for p_name, p_data in self.profiles.items():
            if p_name == "prose":
                self.correctors[p_name] = None
                continue
            raw_lex = p_data.get("lex", []) if isinstance(p_data, dict) else []
            profile_lex: List[str] = raw_lex if isinstance(raw_lex, list) else []
            base_lex: List[str] = self.base_lexicon if isinstance(self.base_lexicon, list) else []
            # Merge base lexicon + profile lexicon without duplicates
            combined = list(dict.fromkeys(base_lex + profile_lex))
            self.correctors[p_name] = TechCorrector(combined, self.learned)

    def get_corrector(self, profile_name: str):
        return self.correctors.get(profile_name)

    def get_prompt(self, profile_name: str, fallback_prompt: str = "") -> str:
        p_data = self.profiles.get(profile_name)
        if p_data and p_data.get("prompt"):
            return p_data["prompt"]
        return fallback_prompt
