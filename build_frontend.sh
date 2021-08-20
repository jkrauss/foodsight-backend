echo "starting to build frontend.."
cd client
NODE_OPTIONS="--max-old-space-size=4096"
npm install
npm run build
rm -r ./node_modules
cd ..
echo "..frontend is built."