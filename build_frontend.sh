echo "starting to build frontend.."
cd client
npm install -g npm
npm install
npm run build
rm -r ./node_modules
cd ..
echo "..frontend is built."
pip install --upgrade pip 