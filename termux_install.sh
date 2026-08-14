#!/data/data/com.termux/files/usr/bin/bash
set -e
pkg update -y
pkg upgrade -y
pkg install -y python git libjpeg-turbo libpng clang make openssl
python -m pip install --upgrade pip wheel setuptools
mkdir -p ~/BotGuardianEnterprise
cp -r ./* ~/BotGuardianEnterprise/
cd ~/BotGuardianEnterprise
python -m pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
fi
echo "Done. Edit ~/BotGuardianEnterprise/.env then run:"
echo "cd ~/BotGuardianEnterprise && python -m botguardian.bot"
