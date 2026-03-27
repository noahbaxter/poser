#pragma once

#include <cstring>
#include <cmath>
#include "AudioFFT.h"
#include "CurveData.h"

// FFT-based magnitude EQ processor.
// Applies curve data to audio via overlap-add with sqrt-Hann windowing.

class EqProcessor
{
public:
    static constexpr int kFFTSize = 1024;
    static constexpr int kHopSize = kFFTSize / 2;
    static constexpr int kComplexSize = kFFTSize / 2 + 1;

    void prepare(double sampleRate)
    {
        fft.init(static_cast<size_t>(kFFTSize));

        // Sqrt-Hann window (analysis * synthesis = Hann → perfect reconstruction at 50% overlap)
        for (int i = 0; i < kFFTSize; ++i)
        {
            float hann = 0.5f * (1.0f - std::cos(2.0f * 3.14159265358979f
                                                   * static_cast<float>(i) / static_cast<float>(kFFTSize)));
            window[i] = std::sqrt(hann);
        }

        // Bin mapping: linear FFT bins → nearest CurveData log-spaced bin
        for (int i = 0; i < kComplexSize; ++i)
        {
            float fftFreq = static_cast<float>(i) * static_cast<float>(sampleRate) / static_cast<float>(kFFTSize);
            int bestIdx = 0;
            float bestDist = std::abs(fftFreq - ::CurveData::kFrequencies[0]);
            for (int j = 1; j < ::CurveData::kNumBins; ++j)
            {
                float dist = std::abs(fftFreq - ::CurveData::kFrequencies[static_cast<size_t>(j)]);
                if (dist < bestDist) { bestDist = dist; bestIdx = j; }
            }
            binMapping[i] = bestIdx;
        }

        reset();
    }

    void reset()
    {
        std::memset(inputFifo, 0, sizeof(inputFifo));
        std::memset(outputAccum, 0, sizeof(outputAccum));
        std::memset(fftRe, 0, sizeof(fftRe));
        std::memset(fftIm, 0, sizeof(fftIm));
        std::memset(fftOut, 0, sizeof(fftOut));
        fifoPos = 0;
        outReadPos = 0;
        for (int i = 0; i < kComplexSize; ++i)
            magnitudeResponse[i] = 1.0f;
    }

    // Build the magnitude response from current curve selections.
    struct CurveParams
    {
        int micSel, cabSel, speakerSel, positionSel;
        float micBlend, cabBlend, speakerBlend, positionBlend;
        float masterPush;
        float lowCutHz, highCutHz;
        int curveMode;
        bool cabFilter;
        bool gainComp;
        double sampleRate;
    };

    void updateResponse(const CurveParams& p)
    {
        for (int i = 0; i < kComplexSize; ++i)
        {
            int cb = binMapping[i];
            float totalDb = 0.0f;

            if (p.micBlend > 0.0f && p.micSel >= 0 && p.micSel < ::CurveData::kNumMics)
                totalDb += ::CurveData::kMics[p.micSel].data[cb] * p.micBlend;
            if (p.cabBlend > 0.0f && p.cabSel >= 0 && p.cabSel < ::CurveData::kNumCabs)
                totalDb += ::CurveData::kCabs[p.cabSel].data[cb] * p.cabBlend;
            if (p.speakerBlend > 0.0f && p.speakerSel >= 0 && p.speakerSel < ::CurveData::kNumSpeakers)
                totalDb += ::CurveData::kSpeakers[p.speakerSel].data[cb] * p.speakerBlend;
            if (p.positionBlend > 0.0f && p.positionSel >= 0 && p.positionSel < ::CurveData::kNumPositions)
                totalDb += ::CurveData::kPositions[p.positionSel].data[cb] * p.positionBlend;

            totalDb *= p.masterPush;

            if (p.curveMode == 1 && totalDb < 0.0f) totalDb = 0.0f;
            if (p.curveMode == 2 && totalDb > 0.0f) totalDb = 0.0f;

            float fftFreq = static_cast<float>(i) * static_cast<float>(p.sampleRate) / static_cast<float>(kFFTSize);

            if (fftFreq < p.lowCutHz && p.lowCutHz > 20.0f)
            {
                float fadeStart = p.lowCutHz * 0.5f;
                if (fftFreq <= fadeStart) totalDb = 0.0f;
                else totalDb *= (fftFreq - fadeStart) / (p.lowCutHz - fadeStart);
            }

            if (fftFreq > p.highCutHz && p.highCutHz < 20000.0f)
            {
                float fadeEnd = p.highCutHz * 2.0f;
                if (fftFreq >= fadeEnd) totalDb = 0.0f;
                else totalDb *= 1.0f - (fftFreq - p.highCutHz) / (fadeEnd - p.highCutHz);
            }

            magnitudeResponse[i] = std::pow(10.0f, totalDb / 20.0f);
        }

        // RMS gain compensation — before cab filter so the filter doesn't affect it
        if (p.gainComp)
        {
            float sumSq = 0.0f;
            for (int i = 0; i < kComplexSize; ++i)
                sumSq += magnitudeResponse[i] * magnitudeResponse[i];
            float rms = std::sqrt(sumSq / static_cast<float>(kComplexSize));
            if (rms > 0.001f)
            {
                float comp = 1.0f / rms;
                for (int i = 0; i < kComplexSize; ++i)
                    magnitudeResponse[i] *= comp;
            }
        }

        // Cab/speaker filter applied after compensation — per-cab HPF × per-speaker LPF
        if (p.cabFilter)
        {
            for (int i = 0; i < kComplexSize; ++i)
            {
                int cb = binMapping[i];
                if (p.cabSel >= 0 && p.cabSel < ::CurveData::kNumCabHPFs)
                    magnitudeResponse[i] *= ::CurveData::kCabHPFs[p.cabSel].data[cb];
                if (p.speakerSel >= 0 && p.speakerSel < ::CurveData::kNumSpeakerLPFs)
                    magnitudeResponse[i] *= ::CurveData::kSpeakerLPFs[p.speakerSel].data[cb];
            }
        }
    }

    // Process one sample per channel. Call for each sample in the block.
    // Returns the output sample for the given channel.
    float processSample(int channel, float input)
    {
        inputFifo[channel][fifoPos] = input;

        float out = outputAccum[channel][outReadPos];
        outputAccum[channel][outReadPos] = 0.0f;
        if (!std::isfinite(out)) out = 0.0f;
        return out;
    }

    // Call after processing all channels for a sample to advance the FIFO.
    void advance(int numChannels)
    {
        int accumSize = kFFTSize * 2;
        outReadPos = (outReadPos + 1) % accumSize;
        ++fifoPos;

        if (fifoPos >= kFFTSize)
        {
            for (int ch = 0; ch < numChannels; ++ch)
                processFrame(ch);

            for (int ch = 0; ch < numChannels; ++ch)
                std::memmove(inputFifo[ch], inputFifo[ch] + kHopSize,
                             static_cast<size_t>(kHopSize) * sizeof(float));
            fifoPos = kHopSize;
        }
    }

    int getLatencySamples() const { return kFFTSize; }
    const int* getBinMapping() const { return binMapping; }

private:
    void processFrame(int channel)
    {
        float windowed[kFFTSize];
        for (int i = 0; i < kFFTSize; ++i)
            windowed[i] = inputFifo[channel][i] * window[i];

        fft.fft(windowed, fftRe, fftIm);

        for (int i = 0; i < kComplexSize; ++i)
        {
            fftRe[i] *= magnitudeResponse[i];
            fftIm[i] *= magnitudeResponse[i];
        }

        fft.ifft(fftOut, fftRe, fftIm);

        int accumSize = kFFTSize * 2;
        for (int i = 0; i < kFFTSize; ++i)
        {
            int idx = (outReadPos + i) % accumSize;
            outputAccum[channel][idx] += fftOut[i] * window[i];
        }
    }

    audiofft::AudioFFT fft;
    float window[kFFTSize] = {};
    float inputFifo[2][kFFTSize] = {};
    float outputAccum[2][kFFTSize * 2] = {};
    int fifoPos = 0;
    int outReadPos = 0;
    float fftRe[kComplexSize] = {};
    float fftIm[kComplexSize] = {};
    float fftOut[kFFTSize] = {};
    float magnitudeResponse[kComplexSize] = {};
    int binMapping[kComplexSize] = {};
};
