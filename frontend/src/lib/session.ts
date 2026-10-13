// The visitor's own copy of the sample factory (each "Load sample factory" creates a private project).
const KEY = "pramaan.project";
// Passcodes of the visitor's own projects, so the setup card can show them again. The browser that
// created a project also holds an HttpOnly cookie for it; this copy is only a convenience.
const CODES = "pramaan.passcodes";

export function lastProject(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberProject(pid: string): void {
  try {
    localStorage.setItem(KEY, pid);
  } catch {
    /* storage may be unavailable (private mode); navigation still works */
  }
}

function codes(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(CODES) || "{}") as Record<string, string>;
  } catch {
    return {};
  }
}

export function rememberPasscode(pid: string, code: string): void {
  try {
    localStorage.setItem(CODES, JSON.stringify({ ...codes(), [pid]: code }));
  } catch {
    /* ignore */
  }
}

export function passcodeFor(pid: string): string | null {
  return codes()[pid] ?? null;
}

/** After the owner deletes a project: this browser forgets it and its passcode. */
export function forgetProject(pid: string): void {
  try {
    if (localStorage.getItem(KEY) === pid) localStorage.removeItem(KEY);
    const c = codes();
    delete c[pid];
    localStorage.setItem(CODES, JSON.stringify(c));
  } catch {
    /* ignore */
  }
}
