#!/bin/sh
# Packs the add-on folder into an installable zip (Blender: Preferences > Add-ons > Install from Disk)
cd "$(dirname "$0")" && rm -f zica_image_to_3d.zip && zip -qr zica_image_to_3d.zip zica_image_to_3d -x '*/__pycache__/*' && ls -la zica_image_to_3d.zip
