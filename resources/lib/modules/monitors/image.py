import xbmc
import threading
from typing import Optional, Type
from dataclasses import dataclass
from ..image import ImageColorAnalyzer


@dataclass
class ImageAnalysisConfig:
    radius: str = "20"
    saturation: str = "1.5"
    background_setting: str = "0"

    @classmethod
    def from_skin_settings(cls):
        """Create config from current skin settings"""
        radius = xbmc.getInfoLabel("Skin.String(BlurRadius)") or "20"
        saturation = xbmc.getInfoLabel("Skin.String(BlurSaturation)") or "1.5"
        background_setting = xbmc.getInfoLabel("Skin.String(BackgroundSetting)") or "0"
        return cls(
            radius=radius, saturation=saturation, background_setting=background_setting
        )


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
        self.daemon = True

    def run(self) -> None:
        """Main monitoring loop."""
        monitor = xbmc.Monitor()
        while not self._stop_event.is_set():
            try:
                if self._is_paused():
                    xbmc.Monitor().waitForAbort(2)
                    continue
                if self._not_altus():
                    xbmc.Monitor().waitForAbort(15)
                    continue
                current_config = ImageAnalysisConfig.from_skin_settings()
                current_blur_diffuse = xbmc.getInfoLabel("$VAR[MainBlurDiffuse]")
                if current_config.background_setting == "2" and current_blur_diffuse != self.last_blur_diffuse:
                    xbmc.executebuiltin(f"SetProperty(LastMainBlurDiffuse,{current_blur_diffuse},home)")
                    self.last_blur_diffuse = current_blur_diffuse
                if current_config.background_setting in ["0", "1", "2"]:
                    analyzer_params = {}
                    if current_config.background_setting in ["1", "2"]:
                        analyzer_params.update(
                            {
                                "radius": current_config.radius,
                                "saturation": current_config.saturation,
                            }
                        )
                    self.analyzer_class(**analyzer_params)
                    monitor.waitForAbort(0.2)
                else:
                    monitor.waitForAbort(3)
            except Exception as e:
                xbmc.log(f"Image analysis error: {str(e)}", xbmc.LOGERROR)
                xbmc.Monitor().waitForAbort(0.2)

    def stop(self):
        self._stop_event.set()

    def _is_paused(self) -> bool:
        return xbmc.getInfoLabel("Window(Home).Property(pause_services)") == "true"

    def _not_altus(self) -> bool:
        return xbmc.getSkinDir() != "skin.altus"
