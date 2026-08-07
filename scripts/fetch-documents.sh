#!/usr/bin/env bash
# Downloads the public records the chronicle cites into assets/docs/, so the
# evidence travels with the repository instead of depending on a host staying
# up. Run once from the repo root:
#
#     bash scripts/fetch-documents.sh
#
# Everything here is a document published by the body that issued it, free to
# read and free to redistribute. Nothing private goes in this folder - see the
# note at the top of .gitignore.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p assets/docs

get () {                      # get <destination> <url> <description>
  local dest="$1" url="$2" what="$3"
  if [ -s "$dest" ]; then
    echo "   already have $what"
    return
  fi
  echo "-> $what"
  if curl -fSL --retry 3 --retry-delay 2 -A 'Mozilla/5.0 (VirasatChronicle; +https://github.com/We-Need-To-Talk-About-Canada/LetsTalk)' \
       -o "$dest.part" "$url"; then
    mv "$dest.part" "$dest"
  else
    rm -f "$dest.part"
    echo "   !! could not fetch $what - the site may be blocking automated"
    echo "      requests. Open the URL in a browser and save it to $dest:"
    echo "      $url"
  fi
}

# Joint communication AL CAN 3/2026 from five UN special rapporteurs to the
# Government of Canada, on threats to the life of Moninder Singh. Published by
# OHCHR through its public communications database.
get "assets/docs/ohchr-joint-communication-canada-2026.pdf" \
    "https://spcommreports.ohchr.org/TMResultsBase/DownLoadPublicCommunicationFile?gId=31021" \
    "UN joint communication to Canada on Moninder Singh (OHCHR, gId 31021)"

echo
echo "done. Files in assets/docs/:"
ls -la assets/docs/ 2>/dev/null || true
