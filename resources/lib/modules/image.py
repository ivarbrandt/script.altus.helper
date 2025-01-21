#!/usr/bin/python
# coding: utf-8

from __future__ import division

import xbmc
import xbmcaddon
import xbmcvfs
import os
from PIL import ImageFilter, Image, ImageOps, ImageEnhance, ImageStat
import math
import colorsys
import json
from .helper import *

#################################################################################################

BLUR_CONTAINER = xbmc.getInfoLabel("Skin.String(BlurContainer)") or 100000
LOGO_CONTAINER = xbmc.getInfoLabel("Skin.String(LogoContainer)") or 100001
BLUR_RADIUS = "40"
BLUR_SATURATION = "1.5"
OLD_IMAGE = ""
OLD_LOGO = ""

#################################################################################################


class ImageColorAnalyzer:
    def __init__(self, prop="listitem", file=None, radius=None, saturation=None):
        global OLD_IMAGE, OLD_LOGO

        # Get background image from blur container - only for color processing
        self.image = xbmc.getInfoLabel("Control.GetLabel(%s)" % BLUR_CONTAINER)

        # Get logo with file parameter logic
        self.logo = (
            file
            if file is not None
            else xbmc.getInfoLabel("Control.GetLabel(%s)" % LOGO_CONTAINER)
        )

        self.radius = int(radius) if radius is not None else int(BLUR_RADIUS)
        self.saturation = (
            float(saturation) if saturation is not None else float(BLUR_SATURATION)
        )

        # Determine if we're in video context
        self.is_video_context = xbmc.getCondVisibility(
            "Window.IsVisible(fullscreenvideo) | Window.IsVisible(videoosd)"
        )

        # Set appropriate property suffix based on context
        self.prop_suffix = "_video" if self.is_video_context else ""

        # New clearlogo processing
        if self.logo:
            # If there's a logo, always process it to ensure we don't miss updates
            if self.logo != OLD_LOGO:
                OLD_LOGO = self.logo
                saved_logo = self.save_cropped_logo()
                if saved_logo:
                    # Use different property based on context
                    winprop(f"{prop}_clearlogo_cropped{self.prop_suffix}", saved_logo)
        else:
            if not xbmc.getCondVisibility(
                "Player.HasVideo"
            ):
                OLD_LOGO = ""
                # Clear both properties when appropriate
                winprop(f"{prop}_clearlogo_cropped", "")
                winprop(f"{prop}_clearlogo_cropped_video", "")

        # Original background color processing
        if xbmc.getCondVisibility("Skin.HasSetting(Enable.Fanart)") and self.image:
            if self.image != OLD_IMAGE:
                OLD_IMAGE = self.image

                cache_key = md5hash(self.image)
                colors = self.get_cached_colors(cache_key)

                if colors:
                    self.avgcolor = colors["avgcolor"]
                    self.textcolor = colors["textcolor"]
                else:
                    img = self.process_image()
                    if img:
                        self.avgcolor, self.textcolor = self.color(img)
                        self.cache_colors(cache_key)
                    else:
                        self.avgcolor = "FFCCCCCC"
                        self.textcolor = "FF141515"

                winprop(prop + "_color_noalpha", self.avgcolor[2:])
                winprop(prop + "_color", self.avgcolor)
                winprop(prop + "_textcolor", self.textcolor)

    def save_cropped_logo(self):
        try:
            # Clean the logo path for consistent hashing
            cleaned_path = self.logo.replace("image://", "")
            if cleaned_path.endswith("/"):
                cleaned_path = cleaned_path[:-1]
            cleaned_path = url_unquote(cleaned_path)

            # Create consistent filename
            filename = f"logo_{md5hash(cleaned_path)}.png"
            targetfile = os.path.join(ADDON_DATA_IMG_PATH, filename)

            # Return existing file if already processed
            if xbmcvfs.exists(targetfile):
                return targetfile

            img = _openimage(self.logo, ADDON_DATA_IMG_PATH, filename)
            if not img:
                return None

            img = img.convert("RGBA")
            bbox = img.getbbox()
            if not bbox:
                return None

            img = img.crop(bbox)

            # Resize if needed
            width, height = img.size
            MAX_WIDTH = 400
            if width > MAX_WIDTH:
                ratio = MAX_WIDTH / width
                new_width = MAX_WIDTH
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)

            # Quantize to reduce number of colors while maintaining transparency
            img = img.quantize(colors=256, method=2, kmeans=1).convert("RGBA")

            img.save(targetfile, "PNG", optimize=True)
            return targetfile

        except Exception as e:
            xbmc.log(f"Error processing clearlogo: {str(e)}", 2)
            return None

    def get_cached_colors(self, cache_key):
        try:
            if os.path.exists(COLOR_CACHE_FILE):
                with open(COLOR_CACHE_FILE, "r") as f:
                    cache = json.load(f)
                    return cache.get(cache_key)
        except Exception as e:
            xbmc.log(f"Error reading color cache: {str(e)}", 2)
        return None

    def cache_colors(self, cache_key):
        try:
            cache = {}
            if os.path.exists(COLOR_CACHE_FILE):
                with open(COLOR_CACHE_FILE, "r") as f:
                    try:
                        cache = json.load(f)
                    except json.JSONDecodeError:
                        pass

            cache[cache_key] = {
                "avgcolor": self.avgcolor,
                "textcolor": self.textcolor,
            }

            cache_dir = os.path.dirname(COLOR_CACHE_FILE)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

            with open(COLOR_CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            xbmc.log(f"Error saving to color cache: {str(e)}", 2)

    def process_image(self):
        try:
            filename = (
                md5hash(self.image) + str(self.radius) + str(self.saturation) + ".png"
            )
            img = _openimage(self.image, ADDON_DATA_IMG_PATH, filename)
            if img:
                img.thumbnail((200, 200), Image.LANCZOS)
                img = img.convert("RGB")

                # Analyze image contrast and brightness
                contrast_level, brightness_level = self.analyze_image(img)

                # Adaptive brightness reduction for very bright images
                if brightness_level > 0.7:
                    reducer = ImageEnhance.Brightness(img)
                    reduction_factor = 1 - (brightness_level - 0.7) * 0.5
                    img = reducer.enhance(reduction_factor)

                # Initial color enhancement (adaptive and balanced)
                enhancer = ImageEnhance.Color(img)
                color_enhance_factor = 1.2 + (0.08 * (1 - contrast_level))
                img = enhancer.enhance(color_enhance_factor)

                # Multi-pass adaptive blur
                for i in range(3):
                    blur_radius = self.radius * (i + 1) / 3
                    img = img.filter(ImageFilter.GaussianBlur(blur_radius))

                    # Apply subtle edge preservation for high-contrast images
                    if contrast_level > 0.5:
                        edge_preserve = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
                        img = Image.blend(img, edge_preserve, 0.15 * contrast_level)

                # Adjust contrast (adaptive)
                contrast = ImageEnhance.Contrast(img)
                contrast_factor = 1.04 + (0.04 * (1 - contrast_level))
                img = contrast.enhance(contrast_factor)

                # Final saturation adjustment (adaptive and balanced)
                if self.saturation:
                    converter = ImageEnhance.Color(img)
                    saturation_factor = self.saturation * (
                        1.05 + (0.15 * (1 - contrast_level))
                    )
                    img = converter.enhance(saturation_factor)

                return img

        except Exception as e:
            xbmc.log(f"Error processing image: {str(e)}", 2)
            return None

    def analyze_image(self, img):
        stat = ImageStat.Stat(img)
        r, g, b = stat.mean
        rm, gm, bm = stat.stddev

        # Calculate contrast level
        contrast_level = (
            math.sqrt(0.241 * (rm**2) + 0.691 * (gm**2) + 0.068 * (bm**2)) / 100
        )
        contrast_level = min(contrast_level, 1.0)

        # Calculate brightness level
        brightness_level = (r + g + b) / (3 * 255)

        return contrast_level, brightness_level

    def color(self, img):
        default_color = "FFCCCCCC"
        default_text_color = "FF141515"  # Default to dark text
        min_brightness = 0.65  # Minimum brightness value
        brightness_boost = 0.55  # Amount to boost brightness for dark colors

        def get_luminance(r, g, b):
            r = r / 255 if r <= 10 else ((r / 255 + 0.055) / 1.055) ** 2.4
            g = g / 255 if g <= 10 else ((g / 255 + 0.055) / 1.055) ** 2.4
            b = b / 255 if b <= 10 else ((b / 255 + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        def get_contrast_ratio(l1, l2):
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        def get_best_text_color(bg_color):
            bg_luminance = get_luminance(bg_color[0], bg_color[1], bg_color[2])

            white = (255, 255, 255)
            dark = (20, 21, 21)  # FF141515

            white_contrast = get_contrast_ratio(get_luminance(*white), bg_luminance)
            dark_contrast = get_contrast_ratio(get_luminance(*dark), bg_luminance)

            # Bias towards white text (lower number equals higher bias)
            if (
                white_contrast >= dark_contrast * 0.52
            ):  # Adjust this factor to fine-tune
                return "FFFFFFFF"
            else:
                return "FF141515"

        try:
            if img:
                # Resize image for faster processing
                img_resize = img.resize((50, 50))

                # Convert image to RGB mode if it's not
                if img_resize.mode != "RGB":
                    img_resize = img_resize.convert("RGB")

                # Get all pixels
                pixels = list(img_resize.getdata())

                # Create color bins (simplify colors)
                color_bins = {}
                for pixel in pixels:
                    # Simplify RGB values to reduce color space
                    simple_color = (pixel[0] // 10, pixel[1] // 10, pixel[2] // 10)
                    if simple_color in color_bins:
                        color_bins[simple_color] += 1
                    else:
                        color_bins[simple_color] = 1

                # Find the most common color
                dominant_color = max(color_bins, key=color_bins.get)

                # Scale the color back up
                r, g, b = [x * 10 for x in dominant_color]

                # Convert to HSV for brightness adjustment
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

                # Apply brightness boost if below minimum brightness
                if v < min_brightness:
                    v = min(v + brightness_boost, 1.0)  # Ensure we don't exceed 1.0

                # Convert back to RGB
                r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(h, s, v)]

                imagecolor = f"FF{r:02x}{g:02x}{b:02x}"
                textcolor = get_best_text_color((r, g, b))

                return imagecolor, textcolor

        except Exception as e:
            xbmc.log(f"Error processing image: {str(e)}", 2)
            return default_color, default_text_color

        return default_color, default_text_color


""" get cached images or copy to temp if file has not been cached yet
"""


def _openimage(image, targetpath, filename):
    # some paths require unquoting to get a valid cached thumb hash
    cached_image_path = url_unquote(image.replace("image://", ""))
    if cached_image_path.endswith("/"):
        cached_image_path = cached_image_path[:-1]

    cached_files = []
    for path in [
        xbmc.getCacheThumbName(cached_image_path),
        xbmc.getCacheThumbName(image),
    ]:
        cached_files.append(
            os.path.join("special://profile/Thumbnails/", path[0], path[:-4] + ".jpg")
        )
        cached_files.append(
            os.path.join("special://profile/Thumbnails/", path[0], path[:-4] + ".png")
        )
        cached_files.append(
            os.path.join("special://profile/Thumbnails/Video/", path[0], path)
        )

    for i in range(1, 4):
        try:
            # Try cached files first
            for cache in cached_files:
                if xbmcvfs.exists(cache):
                    try:
                        with Image.open(xbmcvfs.translatePath(cache)) as img:
                            return img.copy()
                    except Exception as error:
                        xbmc.log(
                            "Image error: Could not open cached image --> %s" % error, 2
                        )

            # Try skin images
            if xbmc.skinHasImage(image):
                if not image.startswith("special://skin"):
                    image = os.path.join("special://skin/media/", image)

                try:
                    with Image.open(xbmcvfs.translatePath(image)) as img:
                        return img.copy()
                except Exception:
                    return ""

            # For other images (including resource://)
            else:
                temp_file = os.path.join(targetpath, "temp_" + filename)
                try:
                    # Copy to temp file
                    if xbmcvfs.copy(image, temp_file):
                        # Load the image
                        with Image.open(temp_file) as img:
                            image_copy = img.copy()
                        # Delete temp file
                        xbmcvfs.delete(temp_file)
                        return image_copy
                except Exception as error:
                    xbmc.log(f"Error processing temporary file: {str(error)}", 2)
                    # Ensure temp file is deleted even if there's an error
                    if xbmcvfs.exists(temp_file):
                        xbmcvfs.delete(temp_file)
                    return ""

        except Exception as error:
            xbmc.log(
                "Image error: Could not get image for %s (try %d) -> %s"
                % (image, i, error),
                2,
            )
            xbmc.sleep(500)
            pass

    return ""
