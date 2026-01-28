"""Tests for sound effects module."""

from __future__ import annotations

import pytest

from src.core.sounds import (
    SoundEffect,
    SoundPlayer,
    get_sound_player,
    set_sounds_enabled,
)


class TestSoundEffect:
    """Tests for SoundEffect enum."""

    def test_sound_effects_exist(self):
        """Test that expected sound effects exist."""
        assert SoundEffect.NEW_OPPORTUNITY
        assert SoundEffect.ALERT
        assert SoundEffect.REFRESH_COMPLETE
        assert SoundEffect.ERROR


class TestSoundPlayer:
    """Tests for SoundPlayer class."""

    def test_player_creation(self):
        """Test SoundPlayer can be created."""
        player = SoundPlayer()
        assert player.enabled is True

    def test_player_disabled(self):
        """Test SoundPlayer can be disabled."""
        player = SoundPlayer(enabled=False)
        assert player.enabled is False

    def test_enable_toggle(self):
        """Test enabling/disabling sounds."""
        player = SoundPlayer()
        assert player.enabled is True

        player.enabled = False
        assert player.enabled is False

        player.enabled = True
        assert player.enabled is True

    def test_play_when_disabled_does_nothing(self):
        """Test that play() does nothing when disabled."""
        player = SoundPlayer(enabled=False)
        # Should not raise any errors
        player.play(SoundEffect.ALERT)
        player.play_new_opportunity()
        player.play_alert()
        player.play_error()


class TestGlobalSoundPlayer:
    """Tests for global sound player functions."""

    def test_get_sound_player_singleton(self):
        """Test that get_sound_player returns the same instance."""
        player1 = get_sound_player()
        player2 = get_sound_player()
        assert player1 is player2

    def test_set_sounds_enabled(self):
        """Test global enable/disable."""
        player = get_sound_player()

        set_sounds_enabled(False)
        assert player.enabled is False

        set_sounds_enabled(True)
        assert player.enabled is True
