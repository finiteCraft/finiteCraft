
#!/usr/bin/env bash
echo "FiniteCraft installer by @quantumbagel - v1.0-alpha"
read -p "Enter your GitHub email (for ssh-keygen): " name
echo "Please TYPE 'finitecraft' as the 'file to save the key' and *do not set a passphrase"

ssh-keygen -t ed25519 -C "$name"
echo "Please add this text in the 'key' section:"
cat "finitecraft.pub"
xdg-open https://github.com/settings/ssh/new
read -p "When you are done, press enter."
mkdir ../finitecraft_api
cd ../finitecraft_api
GIT_SSH_COMMAND='ssh -i finitecraft -o IdentitiesOnly=yes' git init
"# Welcome to FiniteCraft! \n Your backend has been succesfully set up :)\n *finiteCraft by [@quantumbagel](https://github.com/quantumbagel) and [@Pixelz22](https://github.com/Pixelz22)" > README.md
git add README.md
git commit -m 'finiteCraft setup'
read -p "Please enter your GitHub username: " ghname
git remote add origin ssh://git@github.com/"$ghname"/finitecraft-api.git
git config --add --local core.sshCommand 'ssh -i ../finitecraft/finitecraft'
git push -f --set-upstream origin master


echo "finiteCraft set up!"