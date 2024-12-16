#!/bin/bash

# Paths to the encrypted files
ENV_FILE_GPG=".env.gpg"
PKL_FILE_GPG="twitter_cookies.pkl.gpg"

PASSPHRASE_FILE="/secure/passphrase.txt"
# Decrypt files
# Decrypt files
gpg --batch --yes --passphrase-fd 0 --pinentry-mode loopback -o .env -d $ENV_FILE_GPG < $PASSPHRASE_FILE
gpg --batch --yes --passphrase-fd 0 --pinentry-mode loopback -o twitter_cookies.pkl -d $PKL_FILE_GPG < $PASSPHRASE_FILE

# Optionally, remove the encrypted files after decryption
rm $ENV_FILE_GPG
rm $PKL_FILE_GPG
