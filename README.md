# Dr. Keshav Agarwal - Professional Website

Professional website for Dr. Keshav Agarwal, Expert Urologist specializing in Robotic Surgery and Minimally Invasive Urology.

## About

This website showcases Dr. Agarwal's professional credentials, achievements, and expertise in urology. Dr. Agarwal is a distinguished urologist with exceptional academic achievements, including gold medals from AIIMS, New Delhi, and specialized training in Robotics and Minimally Invasive Urology.

## Features

- **Responsive Design**: Fully responsive single-page design optimized for desktop, tablet, and mobile devices
- **Professional Aesthetic**: Clean, minimal design with predominantly white backgrounds and strategic burgundy accents
- **WhatsApp Integration**: Easy consultation scheduling through WhatsApp
- **Comprehensive CV Presentation**: Detailed qualifications, experience, achievements, and publications
- **Scroll Animations**: Smooth fade-in effects and active section highlighting
- **SEO Optimized**: Complete meta tags, Open Graph, Twitter Cards, and structured data

## Sections

- **Hero**: Professional photo and key credentials
- **About**: Professional summary and background
- **Qualifications**: Educational achievements with gold medal highlights
- **Expertise**: Specialized areas of practice
- **Experience**: Professional timeline with current and past positions
- **Achievements**: International and national awards
- **Publications**: Peer-reviewed research articles
- **Contact**: Location, email, phone, and WhatsApp integration

## Technical Stack

- **HTML5**: Semantic markup with accessibility features
- **CSS3**: Custom styles with CSS variables, animations, and responsive design
- **Vanilla JavaScript**: Smooth scrolling, mobile menu, scroll animations, and active navigation
- **Cloudflare Pages**: Automatic deployment from main branch with global CDN

### Deployment

This site is deployed on Cloudflare Pages with automatic deployments triggered by pushes to the main branch.

**Build Configuration**:
- Framework preset: None (static site)
- Build command: `npx wrangler deploy`
- Build output directory: `.` (root)
- Project name: `keshav-uro`

**Features**:
- Automatic deployments on git push
- Preview deployments for all branches
- Custom security headers via `_headers` file
- Custom 404 error page
- Global CDN with edge caching

**Configuration Files**:
- `wrangler.jsonc` - Wrangler configuration for deployment
- `_headers` - Custom HTTP headers for security and caching
- `_redirects` - URL redirect rules for clean URLs
- `404.html` - Custom error page

## Cloudflare Pages Setup

If you need to recreate the Cloudflare Pages deployment:

1. Log in to your Cloudflare account
2. Navigate to **Workers & Pages**
3. Click **Create application** > **Pages** > **Connect to Git**
4. Select **GitHub** and authorize Cloudflare to access your repository
5. Select the `nitishagar/keshav.uro.github.io` repository
6. Configure build settings:
   - **Project name**: `keshav-uro`
   - **Production branch**: `main`
   - **Framework preset**: None
   - **Build command**: `npx wrangler deploy`
   - **Build output directory**: `.`
7. Click **Save and Deploy**

The site will be available at `https://keshav-uro.pages.dev` within minutes.

### Custom Domain

To configure the custom domain `uro-care.com`:

1. In your Cloudflare Pages project, go to **Custom domains**
2. Click **Set up a domain**
3. Enter `uro-care.com` (or `www.uro-care.com`)
4. Since the domain is already on Cloudflare, DNS will be configured automatically
5. Cloudflare will automatically provision SSL/TLS certificates
6. Repeat for both apex and www subdomain if you want both

## Contact

- **Email**: keshavagar@gmail.com
- **Phone**: +91 9818442016
- **WhatsApp**: [Message Dr. Agarwal](https://wa.me/919818442016)
- **Location**: Yashoda Medicity, Niti Khand 3, Shakti Khand 2, Indirapuram, Ghaziabad, Uttar Pradesh 201014

## License

© 2025 Dr. Keshav Agarwal. All rights reserved.

## Disclaimer

The information provided on this website is for general informational purposes only and does not constitute medical advice. Please consult with Dr. Agarwal for personalized medical consultation.
