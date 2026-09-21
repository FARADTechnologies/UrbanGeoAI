/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Panel tamamen tarayıcıda çalışıyor ve veriyi statik JSON'dan okuyor;
  // sunucu gerekmediği için Firebase Hosting'e düz dosya olarak gidiyor.
  output: "export",
  transpilePackages: [
    "@deck.gl/core",
    "@deck.gl/geo-layers",
    "@deck.gl/layers",
    "@deck.gl/react"
  ]
};

export default nextConfig;
