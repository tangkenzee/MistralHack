import { useState } from "react";
import { useNavigate } from "react-router-dom";
import heroCollage from "@/assets/hero-collage.jpg";

const FacebookLogo = () => (
  <svg viewBox="0 0 36 36" className="w-14 h-14" fill="hsl(214, 89%, 52%)">
    <path d="M20.181 35.87C29.094 34.791 36 27.202 36 18c0-9.941-8.059-18-18-18S0 8.059 0 18c0 8.442 5.811 15.526 13.652 17.471L14 26h-4v-8h4v-5.5c0-4.694 2.806-7.5 7-7.5 1.778 0 3 .5 3 .5v4h-2c-1.95 0-3 1.313-3 3V18h5l-1 8h-4l.181 9.87z" />
  </svg>
);

const Index = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="flex flex-col lg:flex-row items-center gap-10 lg:gap-20 max-w-[1100px] w-full">
          {/* Left side - Hero */}
          <div className="flex-1 max-w-[500px]">
            <FacebookLogo />
            <div className="mt-6 relative">
              <img
                src={heroCollage}
                alt="Explore the things you love"
                className="w-full rounded-2xl"
              />
            </div>
            <h1 className="mt-6 text-4xl md:text-5xl font-bold leading-tight text-foreground">
              Explore<br />the things<br />you <span className="text-primary italic">love</span>.
            </h1>
          </div>

          {/* Right side - Login form */}
          <div className="w-full max-w-[400px] bg-card rounded-lg shadow-lg p-6">
            <button
              onClick={() => navigate(-1)}
              className="text-foreground mb-2"
            >
              <span className="text-sm">‹</span>
            </button>
            <h2 className="text-lg font-semibold text-foreground mb-6">
              Log in to Facebook
            </h2>

            <div className="space-y-3">
              <input
                type="text"
                placeholder="Email address or mobile number"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3.5 border border-border rounded-lg text-base bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3.5 border border-border rounded-lg text-base bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <button className="w-full mt-4 py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-base hover:opacity-90 transition-opacity">
              Log in
            </button>

            <button
              onClick={() => navigate("/find-account")}
              className="w-full mt-3 py-3 rounded-lg border border-primary text-primary font-semibold text-base hover:bg-secondary transition-colors"
            >
              Forgotten password?
            </button>

            <hr className="my-5 border-border" />

            <button className="w-full py-3 rounded-lg border border-primary text-primary font-semibold text-base hover:bg-secondary transition-colors">
              Create new account
            </button>

            <div className="flex justify-center mt-6">
              <svg viewBox="0 0 200 40" className="h-6 text-muted-foreground">
                <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fill="currentColor" fontSize="28" fontFamily="Helvetica, Arial" fontWeight="700">
                  ∞ Meta
                </text>
              </svg>
            </div>
          </div>
        </div>
      </main>

      {/* Language bar */}
      <div className="flex justify-center flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground px-4 pb-4">
        {["English (UK)", "中文(简体)", "한국어", "日本語", "Français (France)", "Español", "Deutsch", "More languages..."].map((l) => (
          <a key={l} href="#" className="hover:underline">{l}</a>
        ))}
      </div>
    </div>
  );
};

export default Index;
