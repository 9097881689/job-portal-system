# SEO and Blogger Theme Setup

## Robots.txt

Use this custom robots.txt in Blogger settings:

```txt
User-agent: *
Disallow: /search
Allow: /

Sitemap: https://www.example.com/sitemap.xml
Sitemap: https://www.example.com/atom.xml?redirect=false&start-index=1&max-results=500
```

Replace `https://www.example.com` with your custom domain.

## Google Search Console

1. Add your custom domain property in Search Console.
2. Verify DNS ownership or use the HTML meta tag in Blogger theme.
3. Submit:
   - `/sitemap.xml`
   - `/atom.xml?redirect=false&start-index=1&max-results=500`

## Google Analytics

Add this before `</head>` in the Blogger theme:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

## Homepage Widgets

Add label feed widgets for these labels:

- Latest Jobs
- Government Jobs
- Railway Jobs
- Bank Jobs
- Defence Jobs
- Admit Card
- Results
- Answer Key
- Syllabus

Use Blogger label search URLs, for example:

```html
<a href="/search/label/Latest%20Jobs">Latest Jobs</a>
<a href="/search/label/Admit%20Card">Admit Card</a>
<a href="/search/label/Results">Results</a>
```
