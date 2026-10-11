#!/bin/sh
# Build index.html (GitHub Pages) from src/portal.html.
set -e
cd "$(dirname "$0")"
{
printf '%s\n' '<!doctype html>' '<html lang="en">' '<head>' '<meta charset="utf-8">' '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' '<meta name="description" content="Civic guide and MGNREGA data for Murachh village (Pawai, Panna, Madhya Pradesh): officials, spending, red flags, RTI drafter and complaint channels.">' '<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>' '</head>' '<body>'
sed 's/const STANDALONE=false;/const STANDALONE=true;/' src/portal.html
printf '%s\n' '</body>' '</html>'
} > index.html
echo "built index.html"
