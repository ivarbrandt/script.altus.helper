import xbmc, xbmcgui
import threading
import time
from typing import Optional, Type
from dataclasses import dataclass
from ..image import ImageColorAnalyzer
from ..config import BLUR_CONTAINER, LOGO_CONTAINER

# Loop cadence while a background mode is active.
POLL_INTERVAL = 0.2
# Blur radius/saturation and BackgroundSetting only change in Skin Settings, so
# reading three skin strings every tick bought nothing.
CONFIG_CHECK_INTERVAL = 5
# How soon an analysis that did not finish — blur not generated, video logo not
# cropped or its colour not decoded — is attempted again for the same inputs.
RETRY_INTERVAL = 5


@dataclass
class ImageAnalysisConfig:
    radius: str = "20"
    saturation: str = "1.0"
    background_setting: str = "0"

    @classmethod
    def from_skin_settings(cls):
        """Create config from current skin settings"""
        radius = xbmc.getInfoLabel("Skin.String(BlurRadius)") or "20"
        saturation = xbmc.getInfoLabel("Skin.String(BlurSaturation)") or "1.0"
        background_setting = xbmc.getInfoLabel("Skin.String(BackgroundSetting)") or "0"
        return cls(
            radius=radius, saturation=saturation, background_setting=background_setting
        )
    
    def has_setting_changes(self, other_config):
        """Check if radius or saturation have changed"""
        return self.radius != other_config.radius or self.saturation != other_config.saturation


class ImageMonitor(threading.Thread):
    """Monitors and analyzes images in a separate thread."""

    def __init__(
        self,
        analyzer_class: Type[ImageColorAnalyzer],
        config: Optional[ImageAnalysisConfig] = None,
    ):
        super().__init__()
        self.analyzer_class = analyzer_class
        self.last_blur_diffuse = None
        self.config = config or ImageAnalysisConfig()
        self._stop_event = threading.Event()
        self._restart_event = threading.Event()
        self._home = xbmcgui.Window(10000)
        self.daemon = True

    def run(self) -> None:
        """Main monitoring loop.

        Builds an analyzer only when one of its inputs changes. It used to build
        one every 200ms regardless, and each build republished the background
        colours, touched the blur file on disk, and — during fullscreen video —
        decoded and colour-analysed the clearlogo with PIL, five times a second
        for a logo that does not change for the length of the film.
        """
        monitor = xbmc.Monitor()
        latest = self.config
        last_config_check = 0.0
        last_sig = None
        retry_sig = None
        last_attempt = 0.0
        while not self._stop_event.is_set():
            try:
                if self._restart_event.is_set():
                    self._restart_event.clear()
                    last_sig = retry_sig = None
                    continue
                if self._is_paused():
                    monitor.waitForAbort(2)
                    continue
                if self._not_altus():
                    monitor.waitForAbort(15)
                    continue
                now = time.monotonic()
                if now - last_config_check >= CONFIG_CHECK_INTERVAL:
                    last_config_check = now
                    latest = ImageAnalysisConfig.from_skin_settings()
                    if self.config.has_setting_changes(latest):
                        xbmcgui.Dialog().notification(
                            "Settings Change Detected",
                            "Restarting Image Monitor",
                            "special://skin/resources/icon.jpg",
                            3000
                        )
                        xbmc.log(f"Image Monitor: Settings changed - Radius: {self.config.radius}->{latest.radius}, Saturation: {self.config.saturation}->{latest.saturation}", xbmc.LOGINFO)
                        self.config = latest
                        self.restart()
                        continue
                if latest.background_setting not in ["0", "1", "2"]:
                    monitor.waitForAbort(3)
                    continue
                sig = self._signature(latest.background_setting)
                if sig == last_sig or (
                    sig == retry_sig and now - last_attempt < RETRY_INTERVAL
                ):
                    monitor.waitForAbort(POLL_INTERVAL)
                    continue
                analyzer_params = {}
                if latest.background_setting in ["1", "2"]:
                    analyzer_params.update(
                        {
                            "radius": latest.radius,
                            "saturation": latest.saturation,
                        }
                    )
                # Recorded before building, so an analysis that raises is also
                # held to RETRY_INTERVAL instead of re-running every tick.
                retry_sig, last_attempt = sig, now
                analyzer = self.analyzer_class(**analyzer_params)
                if getattr(analyzer, "settled", True):
                    last_sig = sig
                monitor.waitForAbort(POLL_INTERVAL)
            except Exception as e:
                xbmc.log(f"Image analysis error: {str(e)}", xbmc.LOGERROR)
                monitor.waitForAbort(POLL_INTERVAL)

    def _signature(self, background_setting):
        """Everything the analyzer branches on, read as cheaply as possible.

        If any of these differ from the last settled run, the analyzer has
        something new to do; if none do, it would only repeat itself.
        """
        logo = xbmc.getInfoLabel("Control.GetLabel(%s)" % LOGO_CONTAINER)
        sig = (
            background_setting,
            xbmc.getInfoLabel("Control.GetLabel(%s)" % BLUR_CONTAINER),
            logo,
            xbmc.getCondVisibility("Player.HasVideo"),
            xbmc.getCondVisibility("Window.IsVisible(VideoFullScreen.xml)"),
            # Gates _process_logo. Without it, a logo that changed while this
            # was false would never be cropped once it became true.
            xbmc.getCondVisibility(
                "Window.IsVisible(Home) | Window.IsVisible(1121) | "
                "[Window.IsVisible(videos) + [Control.IsVisible(50) | "
                "Control.IsVisible(54) | Control.IsVisible(55) | "
                "Control.IsVisible(56) | Control.IsVisible(57)]]"
            ),
        )
        if not logo:
            # The no-logo branch clears the cropped logo only while this holds.
            sig += (
                xbmc.getCondVisibility(
                    "!Player.HasVideo + [ControlGroup(2000).HasFocus | "
                    "Window.IsVisible(videos)]"
                ),
            )
        return sig

    def stop(self):
        """Stop the monitor thread."""
        self._stop_event.set()
        
    def restart(self):
        self._restart_event.set()

    def _is_paused(self) -> bool:
        return self._home.getProperty("pause_services") == "true"

    def _not_altus(self) -> bool:
        return xbmc.getSkinDir() != "skin.altus"