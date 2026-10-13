#!/usr/bin/env bash
set -euo pipefail

app_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
demo_dir="$app_root/docs/demo"
capture_dir=$(mktemp -d)
trap 'rm -rf "$capture_dir"' EXIT

mkdir -p "$demo_dir"
npm --prefix "$app_root/browser-tests" run capture -- "$capture_dir"

ffmpeg -hide_banner -loglevel error -y -i "$capture_dir/capture.webm" \
  -vf "setpts=PTS/1.15,fps=24,scale=960:540:flags=lanczos" \
  -c:v libx264 -crf 30 -preset slow -pix_fmt yuv420p -movflags +faststart \
  "$demo_dir/offline-paper-workbench.mp4"

ffmpeg -hide_banner -loglevel error -y -i "$capture_dir/capture.webm" \
  -filter_complex "[0:v]setpts=PTS/1.15,fps=3,scale=420:236:flags=lanczos,split[a][b];[a]palettegen=max_colors=32:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3" \
  -loop 0 "$demo_dir/offline-paper-workbench.gif"

ffmpeg -hide_banner -loglevel error -y -ss 1 -i "$capture_dir/capture.webm" \
  -frames:v 1 "$demo_dir/poster.png"
printf 'DEMO_MEDIA_OK gif=%s mp4=%s poster=%s\n' \
  "$demo_dir/offline-paper-workbench.gif" \
  "$demo_dir/offline-paper-workbench.mp4" \
  "$demo_dir/poster.png"
