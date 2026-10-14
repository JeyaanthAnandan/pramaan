// Signed report receipts, checked in the reader's own browser: WebCrypto verifies the ECDSA P-256
// signature over the exact statement text, and hashes a dropped-in file to compare with the one issued.
// Nothing about the file leaves the browser.

export interface ReceiptStatement {
  schema: string;
  id: string;
  kind: "report.pdf" | "verifier-pack" | "buyer-link";
  issued_at: string;
  project: { id: string; company: string; period: string; fictional_sample: boolean };
  report: { computed_at: string; run_id?: string; code_version: string };
  headline: {
    lines: { line: string; product: string; cn: string; see_t_co2_per_t: string; buyer_declares_2026: string }[];
    buyer_saves_eur_per_year?: string;
    lines_on_actual_data?: string;
  };
  values: { total: number; two_readers_agree: number; approved_as_read: number; changed_by_hand: number; waiting_for_review: number };
  fingerprints: {
    calculation_tree: string;
    values: string;
    source_documents: { file: string; sha256: string }[];
    reference_data: string;
    change_log: { entries: number; head: string; intact: boolean };
    files: Record<string, string>;
  };
}

export interface ReceiptChange { seq: number; at: string; actor: string; action: string; subject?: string; before?: Record<string, unknown> | null; after?: Record<string, unknown> | null }

export interface Receipt {
  id: string;
  statement: ReceiptStatement;
  statement_json: string;
  signature: string;
  signature_raw: string;
  alg: string;
  key: { name: string; pem: string | null; fingerprint: string | null; trusted: boolean };
  signature_valid: boolean;
  now:
    | { project: "deleted" }
    | {
        project: "exists";
        values_match: boolean;
        calculation_matches: boolean;
        log: { ok: boolean; entries: number; broken_at: number | null };
        log_matches_receipt: boolean;
        changes_since: ReceiptChange[];
      };
}

function bytes(b64: string): Uint8Array {
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

/** True if the statement text is exactly what the key signed. Throws if the browser has no WebCrypto. */
export async function verifyInBrowser(pem: string, statementJson: string, signatureRaw: string): Promise<boolean> {
  const der = bytes(pem.replace(/-----[^-]+-----/g, "").replace(/\s+/g, ""));
  const key = await crypto.subtle.importKey("spki", der, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  return crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, bytes(signatureRaw), new TextEncoder().encode(statementJson));
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const h = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(h), (b) => b.toString(16).padStart(2, "0")).join("");
}
