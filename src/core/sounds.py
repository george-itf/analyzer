"""Sound effects for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
import platform
import subprocess
from enum import Enum
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class SoundEffect(Enum):
    """Available sound effects."""

    NEW_OPPORTUNITY = "new_opportunity"  # Score crosses threshold
    ALERT = "alert"  # General alert
    REFRESH_COMPLETE = "refresh_complete"  # Batch refresh done
    ERROR = "error"  # Something went wrong


class SoundPlayer:
    """Cross-platform sound player for alerts."""

    # macOS system sounds that work well for each effect
    MACOS_SOUNDS = {
        SoundEffect.NEW_OPPORTUNITY: "Glass",  # Pleasant chime
        SoundEffect.ALERT: "Ping",  # Notification
        SoundEffect.REFRESH_COMPLETE: "Pop",  # Subtle
        SoundEffect.ERROR: "Basso",  # Low tone for errors
    }

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._system = platform.system()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def play(self, effect: SoundEffect) -> None:
        """Play a sound effect."""
        if not self._enabled:
            return

        try:
            if self._system == "Darwin":  # macOS
                self._play_macos(effect)
            elif self._system == "Windows":
                self._play_windows(effect)
            else:  # Linux/other
                self._play_linux(effect)
        except Exception as e:
            logger.debug(f"Failed to play sound: {e}")

    def _play_macos(self, effect: SoundEffect) -> None:
        """Play sound on macOS using afplay."""
        sound_name = self.MACOS_SOUNDS.get(effect, "Glass")
        sound_path = f"/System/Library/Sounds/{sound_name}.aiff"

        if Path(sound_path).exists():
            subprocess.Popen(
                ["afplay", sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Fallback to system beep
            subprocess.Popen(
                ["osascript", "-e", "beep"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _play_windows(self, effect: SoundEffect) -> None:
        """Play sound on Windows."""
        import winsound

        # Map effects to Windows sounds
        sound_map = {
            SoundEffect.NEW_OPPORTUNITY: winsound.MB_ICONASTERISK,
            SoundEffect.ALERT: winsound.MB_ICONEXCLAMATION,
            SoundEffect.REFRESH_COMPLETE: winsound.MB_OK,
            SoundEffect.ERROR: winsound.MB_ICONHAND,
        }

        winsound.MessageBeep(sound_map.get(effect, winsound.MB_OK))

    def _play_linux(self, effect: SoundEffect) -> None:
        """Play sound on Linux using paplay or aplay."""
        # Try paplay (PulseAudio) first
        try:
            subprocess.Popen(
                ["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            # Fallback to terminal bell
            print("\a", end="", flush=True)

    def play_new_opportunity(self) -> None:
        """Convenience method for new opportunity sound."""
        self.play(SoundEffect.NEW_OPPORTUNITY)

    def play_alert(self) -> None:
        """Convenience method for alert sound."""
        self.play(SoundEffect.ALERT)

    def play_refresh_complete(self) -> None:
        """Convenience method for refresh complete sound."""
        self.play(SoundEffect.REFRESH_COMPLETE)

    def play_error(self) -> None:
        """Convenience method for error sound."""
        self.play(SoundEffect.ERROR)


# Global sound player instance
_sound_player: SoundPlayer | None = None


def get_sound_player() -> SoundPlayer:
    """Get or create the global sound player."""
    global _sound_player
    if _sound_player is None:
        _sound_player = SoundPlayer()
    return _sound_player


def play_sound(effect: SoundEffect) -> None:
    """Play a sound effect using the global player."""
    get_sound_player().play(effect)


def set_sounds_enabled(enabled: bool) -> None:
    """Enable or disable sounds globally."""
    get_sound_player().enabled = enabled
