"""Small synthesized sound effects, so the games need no audio files.

The mixer is only initialized when sound is enabled. On machines without an
audio device initialization fails quietly and the games stay silent.
"""
import numpy as np
import pygame

RATE = 22050


def _tone(freqs, length, decay=8.0, square=False, volume=0.45):
    t = np.arange(int(RATE * length), dtype=np.float32) / RATE
    wave = np.zeros_like(t)
    for f in freqs:
        s = np.sin(2 * np.pi * f * t)
        wave += np.sign(s) * 0.5 if square else s
    wave = wave / max(1, len(freqs)) * np.exp(-t * decay) * volume
    attack = min(len(t), int(RATE * 0.005))
    wave[:attack] *= np.linspace(0, 1, attack)
    return wave


def _sequence(parts):
    return np.concatenate(parts)


def _pop():
    t = np.arange(int(RATE * 0.17), dtype=np.float32) / RATE
    rng = np.random.default_rng()
    return (rng.normal(0, 0.48, len(t)) + 0.75 * np.sin(2 * np.pi * 105 * t)) * np.exp(-t * 25)


def _waves():
    return {
        "pop": _pop(),
        "success": _sequence([_tone([660], 0.09, 10), _tone([880], 0.16, 9)]),
        "miss": _tone([150, 155], 0.22, 9, square=True, volume=0.25),
        "tick": _tone([520], 0.08, 25),
        "go": _tone([880, 1320], 0.3, 6),
        "level_up": _sequence([_tone([523], 0.09, 8), _tone([659], 0.09, 8), _tone([784], 0.22, 6)]),
        "level_down": _sequence([_tone([523], 0.1, 8), _tone([392], 0.2, 6)]),
        "chest": _sequence([_tone([784], 0.07, 10), _tone([988], 0.07, 10), _tone([1175, 1568], 0.3, 5)]),
        "finish": _sequence([_tone([523, 659], 0.15, 5), _tone([659, 784], 0.15, 5), _tone([784, 1047], 0.45, 3)]),
    }


class SoundBoard:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.muted = False
        self.sounds = {}
        if enabled:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
                for name, wave in _waves().items():
                    samples = np.asarray(np.clip(wave, -1, 1) * 32767, dtype=np.int16)
                    self.sounds[name] = pygame.mixer.Sound(buffer=samples.tobytes())
            except (pygame.error, OSError):
                self.enabled = False
                self.sounds = {}

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is not None and not self.muted:
            sound.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted
