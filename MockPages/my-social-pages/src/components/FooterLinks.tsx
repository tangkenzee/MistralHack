const languages = [
  "English (UK)", "中文(简体)", "한국어", "日本語",
  "Français (France)", "Español", "Deutsch", "More languages..."
];

const footerLinks = [
  ["Sign up", "Log in", "Messenger", "Facebook Lite", "Video", "Meta Pay", "Meta Store", "Meta Quest", "Ray-Ban Meta", "Meta AI", "Meta AI more content"],
  ["Instagram", "Threads", "Voting Information Centre", "Privacy Policy", "Privacy Centre", "About", "Create ad", "Create Page", "Developers", "Careers"],
  ["Cookies", "AdChoices", "Terms", "Help", "Contact uploading and non-users"],
];

const FooterLinks = () => (
  <footer className="w-full max-w-[980px] mx-auto mt-6 px-4 pb-6">
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground mb-2">
      {languages.map((lang) => (
        <a key={lang} href="#" className="hover:underline">{lang}</a>
      ))}
    </div>
    <hr className="border-border my-2" />
    <div className="space-y-1">
      {footerLinks.map((row, i) => (
        <div key={i} className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {row.map((link) => (
            <a key={link} href="#" className="hover:underline">{link}</a>
          ))}
        </div>
      ))}
    </div>
    <p className="text-xs text-muted-foreground mt-4">Meta © 2026</p>
  </footer>
);

export default FooterLinks;
