#!/bin/bash
set -e

echo "🔧 تثبيت المتطلبات..."

apt-get update -qq
apt-get install -y ffmpeg -qq

pip install openai python-dotenv -q

mkdir -p assets/fonts uploads output

echo "📥 تنزيل فونت Cairo Bold..."
wget -q "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf" \
     -O assets/fonts/Cairo-Bold.ttf

echo "✅ البيئة جاهزة!"
