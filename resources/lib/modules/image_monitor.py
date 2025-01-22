# import xbmc
# import threading
# from typing import Optional, Type
# from dataclasses import dataclass
# from .image import ImageColorAnalyzer

# @dataclass
# class ImageAnalysisConfig:
#     """Configuration for image analysis."""
#     radius: str = "40"
#     saturation: str = "1.5"

# class ImageMonitor(threading.Thread):
#     """Monitors and analyzes images in a separate thread."""
    
#     def __init__(self, analyzer_class: Type[ImageColorAnalyzer], 
#                  config: Optional[ImageAnalysisConfig] = None):
#         super().__init__()
#         self.analyzer_class = analyzer_class
#         self.config = config or ImageAnalysisConfig()
#         self._stop_event = threading.Event()
#         self.daemon = True

#     def run(self) -> None:
#         """Main monitoring loop."""
#         while not self._stop_event.is_set():
#             try:
#                 if self._is_paused():
#                     xbmc.Monitor().waitForAbort(2)
#                     continue
                    
#                 if self._not_altus():
#                     xbmc.Monitor().waitForAbort(15)
#                     continue
                    
#                 # Use the existing ImageColorAnalyzer
#                 self.analyzer_class(
#                     radius=self.config.radius,
#                     saturation=self.config.saturation
#                 )
#                 xbmc.Monitor().waitForAbort(0.2)
                
#             except Exception as e:
#                 xbmc.log(f"Image analysis error: {str(e)}", xbmc.LOGERROR)
#                 xbmc.Monitor().waitForAbort(0.2)

#     def _is_paused(self) -> bool:
#         """Check if services are paused."""
#         return xbmc.getInfoLabel("Window(Home).Property(pause_services)") == "true"

#     def _not_altus(self) -> bool:
#         """Check if we're not using Altus skin."""
#         return xbmc.getSkinDir() != "skin.altus"

#     def stop(self) -> None:
#         """Stop the monitoring thread."""
#         self._stop_event.set()