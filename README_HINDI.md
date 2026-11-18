# NovaShift — Premium Media Studio

NovaShift एक Flask आधारित media workspace है। इसमें link information preview, MP4/MP3 output selection, progress tracking और completed file save करने का interface शामिल है। यह केवल अपनी सामग्री या ऐसी सामग्री के लिए उपयोग करें जिसे डाउनलोड/कन्वर्ट करने की स्पष्ट अनुमति हो।

## जरूरी कानूनी और सुरक्षा बातें
- DRM, paywall, login wall या अन्य access controls को bypass न करें।
- किसी platform की terms और स्थानीय copyright कानूनों का पालन करें। हर platform या URL supported नहीं होता।
- Public launch से पहले मजबूत `SECRET_KEY` और `APP_PASSWORD` सेट करें। Anonymous public downloader न चलाएँ।
- Ad network approval की गारंटी नहीं है। उपयोगी original content, privacy policy, terms, contact details और ad-network policies का पालन आवश्यक हो सकता है।
- Public launch के लिए HTTPS, firewall, backups, monitoring, storage cleanup, abuse reporting और resource limits लगाएँ।

## बिना CMD / PowerShell: browser-based hosting
यह project local computer पर केवल browser से सीधे public नहीं हो सकता। इसे internet पर चलाने के लिए hosting provider/VPS पर deploy करना होगा। ऐसे provider का dashboard चुनें जो Git repository या ZIP upload और environment variables का visual setup देता हो तथा Python, FFmpeg और background jobs support करता हो। इस project का Docker setup VPS पर Docker Compose के लिए है; उसके लिए server-side setup की जरूरत होगी।

## Docker VPS deployment
1. Domain का DNS A record VPS IP पर point करें।
2. VPS पर Docker Engine और Docker Compose install करें।
3. Project folder VPS पर upload करें।
4. `.env.example` को `.env` में copy करके `SECRET_KEY` और `APP_PASSWORD` को मजबूत unique values से बदलें।
5. `docker compose up -d --build` चलाएँ।
6. Caddy या Nginx reverse proxy के पीछे HTTPS लगाएँ। केवल port 80/443 public रखें; app port 8000 सीधे expose न करें।
7. `downloads/` volume की disk usage monitor करें और scheduled cleanup policy बनाएँ।

## Monetization
- AdSense या अन्य ad network के लिए approval apply करें; approval और revenue guaranteed नहीं हैं।
- Ads को download buttons के पास deceptive तरीके से न रखें और invalid clicks/traffic न खरीदें।
- Affiliate links या optional premium features तभी जोड़ें जब वे स्पष्ट, उपयोगी और platform/legal rules के अनुरूप हों।
- Privacy policy, terms of use, copyright/abuse contact और cookie/ad disclosures publish करें।

## Technical notes
- `DOWNLOAD_DIR` output storage location बदलता है; default `./downloads` है।
- FFmpeg Linux (`ffmpeg`) और Windows (`ffmpeg.exe`) दोनों नामों से detect होता है।
- Default source allowlist `youtube.com,youtu.be` है। इसे किसी platform पर बिना अधिकार/अनुमति के use करने के लिए न बढ़ाएँ।
- yt-dlp supported extractors बदल सकते हैं; update और regression testing करें।
