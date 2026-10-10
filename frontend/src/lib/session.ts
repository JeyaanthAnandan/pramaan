// The visitor's own copy of the sample factory (each "Load sample factory" creates a private project).
const KEY = "pramaan.project";

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
