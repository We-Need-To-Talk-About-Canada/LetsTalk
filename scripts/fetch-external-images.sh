#!/usr/bin/env bash
# Downloads the three non-Wikimedia profile photos into assets/img/.
# Run once from the repo root:  bash scripts/fetch-external-images.sh
# Until these exist the page falls back to the original remote URLs, so it
# still renders correctly - this just makes them local and fast.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p assets/img

echo "-> Gurdip Singh Chaggar"
curl -fSL --retry 3 -o "assets/img/gurdip-singh-chaggar.jpg" \
  'https://images.timesnownews.com/thumb/msid-109106062,thumbsize-6724,width-1280,height-720,resizemode-75/109106062.jpg'

echo "-> Parmjit Singh Panjwar"
curl -fSL --retry 3 -o "assets/img/parmjit-singh-panjwar.jpg" \
  'https://images.squarespace-cdn.com/content/v1/540dd9b6e4b05c669b06779a/bc94d459-debb-40b8-ac81-e67da7f125fd/Fvb5D7wXoAIZEhC.jpeg?format=2500w'

echo "-> Jagtar Singh Johal"
curl -fSL --retry 3 -o "assets/img/jagtar-singh-johal.jpg" \
  'https://substackcdn.com/image/fetch/$s_!tv-g!,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F3ed1da79-deef-4ff3-b70e-8b4722bd577c_634x356.jpeg'

echo "-> Mahmood, Fighting for Faith and Nation (book cover)"
curl -fSL --retry 3 -o "assets/img/mahmood-fighting-for-faith-and-nation.jpg" \
  'https://m.media-amazon.com/images/I/61iTxGqcy2L._SL1350_.jpg'

echo "-> Bhindranwale & Kapur Singh in discussion (SikhRI)"
curl -fSL --retry 3 -o "assets/img/bhindranwale-kapur-singh-discussion.jpg" \
  'https://cdn.prod.website-files.com/5e29591964852b5d27d96ea4/665de0239f5bda3af84e8d7b_DrB7Ssfl294VyaJNk93XGpxDSWW6nvd-mz3w3RPWmNFtt7cUBpCqH-nSFKsZ0VbSGwSYQVTgZaOTivlNSMnRzgoH4KdZuY_7Qkg5YtgexyaIsUkrcYFN-il7G-7JAm2iaTHhg6ESvqqoFakuf1-U-r8.jpeg'

echo
echo "Done. Now commit the files in assets/img/."
