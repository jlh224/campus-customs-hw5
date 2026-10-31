/**
 * Desk sounds, made with the Web Audio API (no audio files to license).
 * All quiet and short; the mute button turns them off.
 *   slide()   – a paper note sliding across the desk (each handoff)
 *   resolved()– a rubber-stamp thump + a cheerful little chime (run finished)
 *   signed()  – a stamp thump + two bright notes (human signed everything)
 *   kaching() – a cash-register ring (a check cleared)
 *   thud()    – a soft "no" (a check was refused)
 */
let ctx: AudioContext | null = null;
let muted = localStorage.getItem("desk-muted") === "1";

export const isMuted = () => muted;
export function setMuted(value: boolean) {
  muted = value;
  localStorage.setItem("desk-muted", value ? "1" : "0");
}

function audio(): AudioContext | null {
  if (muted) return null;
  ctx ??= new AudioContext();
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

function noise(ac: AudioContext, seconds: number): AudioBufferSourceNode {
  const buffer = ac.createBuffer(1, Math.ceil(ac.sampleRate * seconds), ac.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const src = ac.createBufferSource();
  src.buffer = buffer;
  return src;
}

function tone(ac: AudioContext, freq: number, start: number, length: number, type: OscillatorType, volume: number) {
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
  osc.connect(gain).connect(ac.destination);
  osc.start(start);
  osc.stop(start + length + 0.02);
}

function thump(ac: AudioContext, at: number, volume = 0.5) {
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.frequency.setValueAtTime(150, at);
  osc.frequency.exponentialRampToValueAtTime(55, at + 0.12);
  gain.gain.setValueAtTime(volume, at);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.18);
  osc.connect(gain).connect(ac.destination);
  osc.start(at);
  osc.stop(at + 0.2);
  const click = noise(ac, 0.04);
  const cg = ac.createGain();
  cg.gain.setValueAtTime(volume * 0.25, at);
  cg.gain.exponentialRampToValueAtTime(0.0001, at + 0.04);
  click.connect(cg).connect(ac.destination);
  click.start(at);
}

export const sounds = {
  slide() {
    const ac = audio();
    if (!ac) return;
    const t = ac.currentTime;
    const src = noise(ac, 0.42);
    const filter = ac.createBiquadFilter();
    filter.type = "bandpass";
    filter.Q.value = 0.8;
    filter.frequency.setValueAtTime(2200, t);
    filter.frequency.exponentialRampToValueAtTime(500, t + 0.4);
    const gain = ac.createGain();
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.07, t + 0.08);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.42);
    src.connect(filter).connect(gain).connect(ac.destination);
    src.start(t);
  },
  resolved() {
    const ac = audio();
    if (!ac) return;
    const t = ac.currentTime;
    thump(ac, t);
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(ac, f, t + 0.16 + i * 0.09, 0.35, "triangle", 0.12));
  },
  signed() {
    const ac = audio();
    if (!ac) return;
    const t = ac.currentTime;
    thump(ac, t, 0.4);
    tone(ac, 880, t + 0.14, 0.25, "sine", 0.1);
    tone(ac, 1318.5, t + 0.24, 0.4, "sine", 0.1);
  },
  kaching() {
    const ac = audio();
    if (!ac) return;
    const t = ac.currentTime;
    const drawer = noise(ac, 0.08);
    const dg = ac.createGain();
    dg.gain.setValueAtTime(0.12, t);
    dg.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
    drawer.connect(dg).connect(ac.destination);
    drawer.start(t);
    tone(ac, 1567.98, t + 0.07, 0.5, "square", 0.04);
    tone(ac, 2093, t + 0.13, 0.7, "triangle", 0.09);
  },
  thud() {
    const ac = audio();
    if (!ac) return;
    tone(ac, 196, ac.currentTime, 0.25, "sine", 0.15);
  },
};
