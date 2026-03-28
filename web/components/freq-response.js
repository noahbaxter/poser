// Frequency response viewer — live spectrum + static EQ curve overlay.
// Fetches curves.bin once for static curve data.
// Polls spectrum.bin at ~60Hz for live post-EQ FFT magnitudes.
//
// Spectrum is auto-normalized so the average level sits near 0 dB on
// the curve scale. Tracks slowly so you see spectral shape, not level.

import { getNativeFunction, getParameterScaled, onParameterChange } from '../lib/juce-bridge.js';
import { scrollDelta } from '../lib/scroll.js';

// ============================================================
// Tuning constants — adjust these to taste
// ============================================================

const POLL_INTERVAL = 16;    // ms between spectrum fetches (~60Hz)

// Auto-normalization (spectrum level tracking)
const NORM_ATTACK  = 0.03;   // per frame — how fast it tracks louder signal (~0.5s)
const NORM_RELEASE = 0.01;  // per frame — how fast it releases when quieter (~5s)
const NOISE_FLOOR  = -80;    // dBFS — below this, hide the spectrum entirely

// Pink tilt — compensates for natural spectral slope of music
// 0 = no tilt, 3 = exact pink compensation, 4.5 = FabFilter-style
const TILT_DB_PER_OCT = 0;
const TILT_REF_FREQ   = 1000;

// Spectrum smoothing
const SPECTRUM_SMOOTHING_OCT = 0.1; // fraction of an octave to average (0 = off, 0.15 = 1/6 octave)
const SPECTRUM_PEAK_ATTACK   = 1.0;  // per frame — how fast peaks appear (1.0 = instant)
const SPECTRUM_PEAK_DECAY    = 0.06; // per frame — how fast peaks fall (~0.3s to half)

// Spectrum visual
const SPECTRUM_FILL_ALPHA   = 0.06;  // fill opacity
const SPECTRUM_STROKE_ALPHA = 0.15;  // outline opacity

// EQ curve visual
const CURVE_FILL_ALPHA   = 0.18;  // fill between curve and 0dB
const CURVE_STROKE_WIDTH = 1.5;

// ============================================================

const MIN_FREQ = 20;
const MAX_FREQ = 20000;
const GRID_FREQS = [50, 100, 200, 500, 1000, 2000, 5000, 10000];

export class FreqResponse {
    constructor(viewerEl, toggleEl, config) {
        this.viewer = viewerEl;
        this.toggle = toggleEl;
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        viewerEl.appendChild(this.canvas);

        this.sampleRate = config.sampleRate;
        this.fftSize = config.fftSize;
        this.spectrumSize = config.spectrumSize;

        this.curveData = null;
        this.compositeDb = null;
        this.spectrumData = null;
        this.open = false;
        this.pollId = null;
        this.w = 0;
        this.h = 0;

        // Auto-normalization state
        this.trackedAvgDb = -40;

        // Per-bin peak-hold buffer (filled on first spectrum frame)
        this.smoothedBins = null;

        // Y-axis scale (manual toggle)
        this.scaleOptions = [6, 12, 24, 36];
        this.scaleIndex = 0;
        this.scale = this.scaleOptions[this.scaleIndex];

        // Scale toggle button
        this.scaleBtn = document.createElement('div');
        this.scaleBtn.className = 'eq-scale-btn';
        this.scaleBtn.textContent = '\u00B1' + this.scale;
        this.scaleBtn.addEventListener('click', () => this.cycleScale(1));
        viewerEl.appendChild(this.scaleBtn);

        // Scroll to change scale — anywhere on the viewer
        const handleScaleScroll = (e) => {
            if (!this.open) return;
            e.preventDefault();
            const delta = scrollDelta(e);
            if (delta === 0) return;
            const dir = delta < 0 ? 1 : -1;
            this.cycleScale(dir);
        };
        viewerEl.addEventListener('wheel', handleScaleScroll, { passive: false });

        // Toggle via native function
        const toggleFn = getNativeFunction('toggleEqViewer');
        toggleEl.addEventListener('click', async () => {
            const isOpen = await toggleFn();
            this.setOpen(isOpen);
        });

        // Load static curve data
        this.loadCurveData();

        // Recompute composite curve on any relevant param change
        const paramIds = [
            'mic_select', 'cab_select', 'speaker_select', 'position_select',
            'mic_blend', 'cab_blend', 'speaker_blend', 'position_blend',
            'master_push', 'curve_low_cut', 'curve_high_cut', 'cab_filter',
        ];
        for (const id of paramIds) {
            onParameterChange(id, () => this.updateCurve());
        }

        // Resize
        const ro = new ResizeObserver(() => {
            if (this.open) { this.resize(); this.draw(); }
        });
        ro.observe(viewerEl);
    }

    setCutKnobs(loCutKnob, hiCutKnob) {
        this.loCutKnob = loCutKnob;
        this.hiCutKnob = hiCutKnob;
        this.loCutOrigMin = loCutKnob.min;
        this.hiCutOrigMax = hiCutKnob.max;
        this.savedLoCut = null;
        this.savedHiCut = null;
        this.loCutTouched = false;
        this.hiCutTouched = false;
        this.wasCabFilter = false;

        // Track if user touches the knobs while FLT is on
        loCutKnob.onChange = () => { if (this.wasCabFilter) this.loCutTouched = true; };
        hiCutKnob.onChange = () => { if (this.wasCabFilter) this.hiCutTouched = true; };
    }

    updateCutRanges(p) {
        const freqs = this.curveData.frequencies;
        const threshold = 0.707; // -3dB

        if (p.cabFilter) {
            // Save values and reset touched flags on FLT toggle-on
            if (!this.wasCabFilter) {
                this.savedLoCut = this.loCutKnob.getValue();
                this.savedHiCut = this.hiCutKnob.getValue();
                this.loCutTouched = false;
                this.hiCutTouched = false;
            }

            // Cab HPF: find -3dB point → new LO CUT minimum
            let hpfCutoff = this.loCutOrigMin;
            if (p.cabSel >= 0 && p.cabSel < this.curveData.cabHPFs.length) {
                const hpf = this.curveData.cabHPFs[p.cabSel];
                for (let i = 0; i < hpf.length; i++) {
                    if (hpf[i] >= threshold) { hpfCutoff = freqs[i]; break; }
                }
            }
            this.loCutKnob.min = Math.max(this.loCutOrigMin, Math.round(hpfCutoff));

            // Speaker LPF: find -3dB point → new HI CUT maximum
            let lpfCutoff = this.hiCutOrigMax;
            if (p.speakerSel >= 0 && p.speakerSel < this.curveData.speakerLPFs.length) {
                const lpf = this.curveData.speakerLPFs[p.speakerSel];
                for (let i = lpf.length - 1; i >= 0; i--) {
                    if (lpf[i] >= threshold) { lpfCutoff = freqs[i]; break; }
                }
            }
            this.hiCutKnob.max = Math.min(this.hiCutOrigMax, Math.round(lpfCutoff));

            // Clamp current values to new ranges
            if (this.loCutKnob.getValue() < this.loCutKnob.min) {
                this.loCutKnob.setValue(this.loCutKnob.min);
            }
            if (this.hiCutKnob.getValue() > this.hiCutKnob.max) {
                this.hiCutKnob.setValue(this.hiCutKnob.max);
            }
        } else {
            // FLT off: restore original ranges
            this.loCutKnob.min = this.loCutOrigMin;
            this.hiCutKnob.max = this.hiCutOrigMax;

            // Only restore saved values if user didn't touch the knob
            if (this.savedLoCut !== null && !this.loCutTouched) {
                this.loCutKnob.setValue(this.savedLoCut);
            }
            if (this.savedHiCut !== null && !this.hiCutTouched) {
                this.hiCutKnob.setValue(this.savedHiCut);
            }
            this.savedLoCut = null;
            this.savedHiCut = null;
        }

        this.wasCabFilter = p.cabFilter;
        this.loCutKnob.render();
        this.hiCutKnob.render();
    }

    cycleScale(direction) {
        this.scaleIndex = Math.max(0, Math.min(this.scaleOptions.length - 1, this.scaleIndex + direction));
        this.scale = this.scaleOptions[this.scaleIndex];
        this.scaleBtn.textContent = '\u00B1' + this.scale;
        this.draw();
    }

    setOpen(isOpen) {
        this.open = isOpen;
        this.toggle.textContent = isOpen ? 'EQ \u25B4' : 'EQ \u25BE';
        if (isOpen) {
            this.startPolling();
            requestAnimationFrame(() => {
                this.resize();
                this.updateCurve();
            });
        } else {
            this.stopPolling();
        }
    }

    // --- Static curve data (fetched once) ---

    async loadCurveData() {
        try {
            const response = await fetch('curves.bin');
            const buffer = await response.arrayBuffer();
            this.curveData = parseCurveBinary(buffer);
            this.updateCurve();
        } catch (e) {
            console.warn('Failed to load curves.bin:', e);
        }
    }

    updateCurve() {
        if (!this.curveData) return;

        const p = {
            micSel:      Math.round(getParameterScaled('mic_select')),
            cabSel:      Math.round(getParameterScaled('cab_select')),
            speakerSel:  Math.round(getParameterScaled('speaker_select')),
            positionSel: Math.round(getParameterScaled('position_select')),
            micBlend:    getParameterScaled('mic_blend'),
            cabBlend:    getParameterScaled('cab_blend'),
            speakerBlend: getParameterScaled('speaker_blend'),
            positionBlend: getParameterScaled('position_blend'),
            masterPush:  getParameterScaled('master_push'),
            lowCutHz:    getParameterScaled('curve_low_cut'),
            highCutHz:   getParameterScaled('curve_high_cut'),
            cabFilter:   getParameterScaled('cab_filter') >= 0.5,
        };

        this.compositeDb = computeCompositeCurve(this.curveData, p);

        // Update LO/HI CUT knob ranges when FLT is on
        if (this.loCutKnob && this.hiCutKnob && this.curveData) {
            this.updateCutRanges(p);
        }

        if (this.open) this.draw();
    }

    // --- Live spectrum (polled) ---

    startPolling() {
        if (this.pollId) return;
        const poll = async () => {
            try {
                const response = await fetch('spectrum.bin');
                const buffer = await response.arrayBuffer();
                this.spectrumData = new Float32Array(buffer);
                if (this.open) this.draw();
            } catch (e) { /* skip frame */ }
        };
        this.pollId = setInterval(poll, POLL_INTERVAL);
    }

    stopPolling() {
        if (this.pollId) {
            clearInterval(this.pollId);
            this.pollId = null;
        }
        this.spectrumData = null;
    }

    // --- Canvas ---

    resize() {
        const rect = this.viewer.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.w = rect.width;
        this.h = rect.height;
    }

    draw() {
        const ctx = this.ctx;
        const w = this.w;
        const h = this.h;
        if (w === 0 || h === 0) return;

        ctx.clearRect(0, 0, w, h);

        const scale = this.scale;

        const pad = { left: 4, right: 4, top: 6, bottom: 16 };
        const pw = w - pad.left - pad.right;
        const ph = h - pad.top - pad.bottom;
        const logMin = Math.log10(MIN_FREQ);
        const logMax = Math.log10(MAX_FREQ);
        const logRange = logMax - logMin;

        const freqToX = (f) => pad.left + pw * (Math.log10(f) - logMin) / logRange;
        const dbToY = (db) => pad.top + ph * (0.5 - db / (scale * 2));

        // Position scale button at top dB line
        this.scaleBtn.style.top = (pad.top - 1) + 'px';

        // --- Grid ---
        ctx.font = '9px "SF Mono", "Menlo", monospace';

        // Frequency grid
        ctx.strokeStyle = '#eee';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#bbb';
        ctx.textAlign = 'center';
        for (const f of GRID_FREQS) {
            if (f < MIN_FREQ || f > MAX_FREQ) continue;
            const x = freqToX(f);
            ctx.beginPath();
            ctx.moveTo(x, pad.top);
            ctx.lineTo(x, pad.top + ph);
            ctx.stroke();
            const label = f >= 1000 ? (f / 1000) + 'k' : String(f);
            ctx.fillText(label, x, h - 3);
        }

        // dB grid (dynamic based on scale)
        ctx.textAlign = 'left';
        for (let db = -scale; db <= scale; db += 6) {
            const y = dbToY(db);
            ctx.strokeStyle = db === 0 ? '#ccc' : '#eee';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(pad.left + pw, y);
            ctx.stroke();
            // Skip top label (scale button replaces it), keep bottom
            if (db !== 0 && db !== scale) {
                ctx.fillStyle = '#bbb';
                ctx.fillText((db > 0 ? '+' : '') + db, pad.left + 4, y + 3);
            }
        }

        // --- Clip to plot area (curves go off-screen, not flat) ---
        ctx.save();
        ctx.beginPath();
        ctx.rect(pad.left, pad.top, pw, ph);
        ctx.clip();

        // --- Live spectrum (background, auto-normalized) ---
        if (this.spectrumData && this.spectrumData.length > 0) {
            const halfN = this.fftSize / 2;
            const binCount = this.spectrumData.length;

            // Convert raw magnitudes to dB with tilt
            const rawDb = new Float32Array(binCount);
            for (let i = 1; i < binCount; i++) {
                const freq = i * this.sampleRate / this.fftSize;
                const mag = this.spectrumData[i];
                const db = mag > 0 ? 20 * Math.log10(mag / halfN) : -120;
                const tilt = TILT_DB_PER_OCT * Math.log2(freq / TILT_REF_FREQ);
                rawDb[i] = db + tilt;
            }

            // Frequency smoothing: window width proportional to frequency
            // At low freqs (few bins/octave) → narrow window; at high freqs → wide window
            const binHz = this.sampleRate / this.fftSize;
            const smoothedDb = new Float32Array(binCount);
            for (let i = 1; i < binCount; i++) {
                const freq = i * binHz;
                // Number of bins in SPECTRUM_SMOOTHING_OCT octaves at this frequency
                const halfWidth = Math.round(freq * (Math.pow(2, SPECTRUM_SMOOTHING_OCT) - 1) / binHz);
                const lo = Math.max(1, i - halfWidth);
                const hi = Math.min(binCount - 1, i + halfWidth);
                let sum = 0;
                for (let j = lo; j <= hi; j++) sum += rawDb[j];
                smoothedDb[i] = sum / (hi - lo + 1);
            }

            // Peak hold: fast attack, slow decay per bin
            if (!this.smoothedBins || this.smoothedBins.length !== binCount) {
                this.smoothedBins = new Float32Array(binCount).fill(-120);
            }
            for (let i = 1; i < binCount; i++) {
                const incoming = smoothedDb[i];
                if (incoming > this.smoothedBins[i]) {
                    this.smoothedBins[i] += (incoming - this.smoothedBins[i]) * SPECTRUM_PEAK_ATTACK;
                } else {
                    this.smoothedBins[i] += (incoming - this.smoothedBins[i]) * SPECTRUM_PEAK_DECAY;
                }
            }

            // Build display bins with auto-normalization average
            const displayBins = [];
            let sumDb = 0, sumWeight = 0;

            for (let i = 1; i < binCount; i++) {
                const freq = i * this.sampleRate / this.fftSize;
                if (freq > MAX_FREQ) break;
                const db = this.smoothedBins[i];
                displayBins.push({ freq: Math.max(freq, MIN_FREQ), db });
                if (freq >= MIN_FREQ) {
                    const weight = 1 / freq;
                    sumDb += db * weight;
                    sumWeight += weight;
                }
            }

            // Extend first bin to left edge
            if (displayBins.length > 0 && displayBins[0].freq > MIN_FREQ) {
                displayBins.unshift({ freq: MIN_FREQ, db: displayBins[0].db });
            }

            const currentAvg = sumWeight > 0 ? sumDb / sumWeight : -120;

            // Smooth the normalization average (attack/release)
            if (currentAvg > NOISE_FLOOR) {
                const alpha = currentAvg > this.trackedAvgDb ? NORM_ATTACK : NORM_RELEASE;
                this.trackedAvgDb += (currentAvg - this.trackedAvgDb) * alpha;
            }

            // Draw spectrum (only if signal present)
            if (this.trackedAvgDb > NOISE_FLOOR) {
                // Fill
                ctx.beginPath();
                let started = false;
                for (const bin of displayBins) {
                    const x = freqToX(bin.freq);
                    const y = dbToY(bin.db - this.trackedAvgDb);
                    if (!started) { ctx.moveTo(x, y); started = true; }
                    else ctx.lineTo(x, y);
                }
                ctx.lineTo(freqToX(displayBins[displayBins.length - 1].freq), pad.top + ph);
                ctx.lineTo(freqToX(displayBins[0].freq), pad.top + ph);
                ctx.closePath();
                ctx.fillStyle = `rgba(0, 0, 0, ${SPECTRUM_FILL_ALPHA})`;
                ctx.fill();

                // Stroke
                ctx.beginPath();
                started = false;
                for (const bin of displayBins) {
                    const x = freqToX(bin.freq);
                    const y = dbToY(bin.db - this.trackedAvgDb);
                    if (!started) { ctx.moveTo(x, y); started = true; }
                    else ctx.lineTo(x, y);
                }
                ctx.strokeStyle = `rgba(0, 0, 0, ${SPECTRUM_STROKE_ALPHA})`;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }

        // --- EQ curve (foreground) ---
        if (this.compositeDb && this.curveData) {
            const freqs = this.curveData.frequencies;
            const N = freqs.length;
            const zeroY = dbToY(0);

            // Fill between curve and 0dB
            ctx.beginPath();
            let started = false;
            let firstX = 0, lastX = 0;
            for (let i = 0; i < N; i++) {
                if (freqs[i] < MIN_FREQ || freqs[i] > MAX_FREQ) continue;
                const x = freqToX(freqs[i]);
                const y = dbToY(this.compositeDb[i]);
                if (!started) { ctx.moveTo(x, y); firstX = x; started = true; }
                else ctx.lineTo(x, y);
                lastX = x;
            }
            ctx.lineTo(lastX, zeroY);
            ctx.lineTo(firstX, zeroY);
            ctx.closePath();
            ctx.fillStyle = `rgba(0, 0, 0, ${CURVE_FILL_ALPHA})`;
            ctx.fill();

            // Stroke
            ctx.beginPath();
            started = false;
            for (let i = 0; i < N; i++) {
                if (freqs[i] < MIN_FREQ || freqs[i] > MAX_FREQ) continue;
                const x = freqToX(freqs[i]);
                const y = dbToY(this.compositeDb[i]);
                if (!started) { ctx.moveTo(x, y); started = true; }
                else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = '#000';
            ctx.lineWidth = CURVE_STROKE_WIDTH;
            ctx.stroke();
        }

        ctx.restore();
    }
}

// --- Binary parsing ---

function parseCurveBinary(buffer) {
    const header = new Uint32Array(buffer, 0, 7);
    const [numBins, numMics, numCabs, numSpeakers, numPositions, numCabHPFs, numSpeakerLPFs] = header;

    let offset = 7 * 4;
    const readFloats = (count) => {
        const arr = new Float32Array(buffer, offset, count);
        offset += count * 4;
        return arr;
    };

    const frequencies = readFloats(numBins);
    const readCurves = (count) => {
        const curves = [];
        for (let i = 0; i < count; i++) curves.push(readFloats(numBins));
        return curves;
    };

    return {
        frequencies,
        mics: readCurves(numMics),
        cabs: readCurves(numCabs),
        speakers: readCurves(numSpeakers),
        positions: readCurves(numPositions),
        cabHPFs: readCurves(numCabHPFs),
        speakerLPFs: readCurves(numSpeakerLPFs),
    };
}

// --- Composite curve computation (mirrors C++ updateResponse, no gain comp) ---

function computeCompositeCurve(curveData, p) {
    const { frequencies, mics, cabs, speakers, positions, cabHPFs, speakerLPFs } = curveData;
    const N = frequencies.length;
    const result = new Float32Array(N);

    for (let i = 0; i < N; i++) {
        let totalDb = 0;

        if (p.micBlend !== 0 && p.micSel >= 0 && p.micSel < mics.length)
            totalDb += mics[p.micSel][i] * p.micBlend;
        if (p.cabBlend !== 0 && p.cabSel >= 0 && p.cabSel < cabs.length)
            totalDb += cabs[p.cabSel][i] * p.cabBlend;
        if (p.speakerBlend !== 0 && p.speakerSel >= 0 && p.speakerSel < speakers.length)
            totalDb += speakers[p.speakerSel][i] * p.speakerBlend;
        if (p.positionBlend !== 0 && p.positionSel >= 0 && p.positionSel < positions.length)
            totalDb += positions[p.positionSel][i] * p.positionBlend;

        totalDb *= p.masterPush;

        // Lo/hi cut fade
        const freq = frequencies[i];
        if (freq < p.lowCutHz && p.lowCutHz > 20) {
            const fadeStart = p.lowCutHz * 0.5;
            if (freq <= fadeStart) totalDb = 0;
            else totalDb *= (freq - fadeStart) / (p.lowCutHz - fadeStart);
        }
        if (freq > p.highCutHz && p.highCutHz < 20000) {
            const fadeEnd = p.highCutHz * 2;
            if (freq >= fadeEnd) totalDb = 0;
            else totalDb *= 1 - (freq - p.highCutHz) / (fadeEnd - p.highCutHz);
        }

        // Cab filter: HPF x LPF (linear -> add dB)
        if (p.cabFilter) {
            if (p.cabSel >= 0 && p.cabSel < cabHPFs.length) {
                const hpf = cabHPFs[p.cabSel][i];
                if (hpf > 0) totalDb += 20 * Math.log10(hpf);
                else totalDb = -100;
            }
            if (p.speakerSel >= 0 && p.speakerSel < speakerLPFs.length) {
                const lpf = speakerLPFs[p.speakerSel][i];
                if (lpf > 0) totalDb += 20 * Math.log10(lpf);
                else totalDb = -100;
            }
        }

        result[i] = totalDb;
    }

    return result;
}
