// Call Pramaan, the browser end: microphone -> 16 kHz PCM16 over a WebSocket to our server, which
// holds the Gemini Live session; the agent's voice comes back as 24 kHz PCM16 and is played in order.
// When the caller talks over the agent, the server says "interrupted" and playback stops at once.

export interface CallFigure { id: string; label: string; value: string; unit: string; node: string | null }
export type CallEvent =
  | { type: "ready"; model: string; lang: string; max_seconds: number }
  | { type: "caption"; who: "caller" | "agent"; text: string }
  | { type: "turn"; said: string; figures: CallFigure[]; unverified: string[]; correction?: boolean }
  | { type: "correcting"; numbers: string[] }
  | { type: "tool"; name: string }
  | { type: "action"; name: "open_evidence"; node: string; label: string }
  | { type: "interrupted" }
  | { type: "ended"; reason: string }
  | { type: "error"; code: string; detail?: string };

export const CALL_LANGS = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
  { code: "pa", label: "ਪੰਜਾਬੀ" },
  { code: "ta", label: "தமிழ்" },
  { code: "vi", label: "Tiếng Việt" },
] as const;

const IN_RATE = 16000;
const OUT_RATE = 24000;

// Resamples the microphone to 16 kHz (averaging the samples between two output points, a cheap
// low-pass) and posts 100 ms of PCM16 at a time, plus a level for the on-screen ring.
const WORKLET = `
class PcmCapture extends AudioWorkletProcessor {
  constructor() { super(); this.step = sampleRate / ${IN_RATE}; this.pos = 0; this.acc = 0; this.cnt = 0;
    this.buf = new Int16Array(${IN_RATE / 10}); this.n = 0; this.sq = 0; this.blocks = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      const v = ch[i]; this.acc += v; this.cnt++; this.sq += v * v; this.pos += 1;
      if (this.pos >= this.step) {
        this.pos -= this.step;
        const s = Math.max(-1, Math.min(1, this.acc / this.cnt)); this.acc = 0; this.cnt = 0;
        this.buf[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.n === this.buf.length) { this.port.postMessage(this.buf.buffer, [this.buf.buffer]); this.buf = new Int16Array(${IN_RATE / 10}); this.n = 0; }
      }
    }
    if (++this.blocks === 8) { this.port.postMessage({ level: Math.sqrt(this.sq / (8 * ch.length)) }); this.blocks = 0; this.sq = 0; }
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
`;

export function callSupported(): boolean {
  return typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof AudioWorkletNode !== "undefined" && typeof WebSocket !== "undefined";
}

export class CallClient {
  private ws: WebSocket | null = null;
  private mic: MediaStream | null = null;
  private inCtx: AudioContext | null = null;
  private outCtx: AudioContext | null = null;
  private sources = new Set<AudioBufferSourceNode>();
  private nextAt = 0;
  private closed = false;
  muted = false;

  constructor(
    private onEvent: (e: CallEvent) => void,
    private onLevel: (who: "caller" | "agent", level: number) => void,
    private onSpeaking: (speaking: boolean) => void,
  ) {}

  /** Ask for the microphone, then open the call. Throws "mic_denied" if the browser says no. */
  async start(pid: string, lang: string): Promise<void> {
    try {
      this.mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    } catch {
      throw new Error("mic_denied");
    }
    this.inCtx = new AudioContext();
    const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
    await this.inCtx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const node = new AudioWorkletNode(this.inCtx, "pcm-capture");
    const silent = this.inCtx.createGain();
    silent.gain.value = 0; // the worklet must be pulled by the graph, but the caller should not hear themselves
    this.inCtx.createMediaStreamSource(this.mic).connect(node).connect(silent).connect(this.inCtx.destination);
    node.port.onmessage = (e: MessageEvent) => {
      if (e.data instanceof ArrayBuffer) {
        if (!this.muted && this.ws?.readyState === WebSocket.OPEN) this.ws.send(e.data);
      } else if (typeof e.data?.level === "number") this.onLevel("caller", this.muted ? 0 : e.data.level);
    };
    try {
      this.outCtx = new AudioContext({ sampleRate: OUT_RATE });
    } catch {
      this.outCtx = new AudioContext(); // buffers carry their own rate; the browser resamples
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/api/projects/${encodeURIComponent(pid)}/call?lang=${lang}`);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (m) => {
      if (m.data instanceof ArrayBuffer) return this.play(m.data);
      let e: CallEvent;
      try {
        e = JSON.parse(m.data as string) as CallEvent;
      } catch {
        return;
      }
      if (e.type === "interrupted") this.flush();
      this.onEvent(e);
    };
    ws.onclose = () => {
      if (!this.closed) this.onEvent({ type: "ended", reason: "closed" });
      this.stop();
    };
    ws.onerror = () => {
      if (!this.closed) this.onEvent({ type: "error", code: "call_failed" });
    };
    this.ws = ws;
  }

  private play(data: ArrayBuffer): void {
    const ctx = this.outCtx;
    if (!ctx || data.byteLength < 2) return;
    const pcm = new Int16Array(data, 0, data.byteLength >> 1);
    const buf = ctx.createBuffer(1, pcm.length, OUT_RATE);
    const ch = buf.getChannelData(0);
    let sq = 0;
    for (let i = 0; i < pcm.length; i++) {
      ch[i] = pcm[i] / 0x8000;
      sq += ch[i] * ch[i];
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    const at = Math.max(ctx.currentTime + 0.02, this.nextAt);
    src.start(at);
    this.nextAt = at + buf.duration;
    this.sources.add(src);
    this.onSpeaking(true);
    this.onLevel("agent", Math.sqrt(sq / Math.max(1, pcm.length)));
    src.onended = () => {
      this.sources.delete(src);
      if (!this.sources.size) {
        this.onSpeaking(false);
        this.onLevel("agent", 0);
      }
    };
  }

  /** Stop the agent's voice now (the caller started talking). */
  flush(): void {
    this.sources.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    });
    this.sources.clear();
    this.nextAt = 0;
    this.onSpeaking(false);
  }

  setMuted(m: boolean): void {
    this.muted = m;
    if (m) this.onLevel("caller", 0);
  }

  sendText(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "text", text }));
  }

  hangup(): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "hangup" }));
    this.stop();
  }

  private stop(): void {
    if (this.closed) return;
    this.closed = true;
    this.flush();
    this.mic?.getTracks().forEach((t) => t.stop());
    void this.inCtx?.close().catch(() => undefined);
    void this.outCtx?.close().catch(() => undefined);
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) this.ws.close();
  }
}
