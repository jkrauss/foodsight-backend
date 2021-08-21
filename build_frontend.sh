echo "starting to build frontend.."
cd client
npm install
npm run build
rm -r ./node_modules
cd ..
echo "..frontend is built."