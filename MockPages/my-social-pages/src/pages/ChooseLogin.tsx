import { useState } from "react";
import { useNavigate } from "react-router-dom";
import BackButton from "@/components/BackButton";
import FooterLinks from "@/components/FooterLinks";
import { User } from "lucide-react";

const ChooseLogin = () => {
  const navigate = useNavigate();
  const [method, setMethod] = useState<"email" | "password">("email");

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex flex-col items-center pt-10 px-4">
        <div className="w-full max-w-[580px]">
          <BackButton />
          <h1 className="text-2xl font-bold text-foreground mb-5">Choose a way to log in</h1>

          {/* User card */}
          <div className="flex items-center gap-3 p-4 border border-border rounded-lg mb-6">
            <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center">
              <User className="w-6 h-6 text-muted-foreground" />
            </div>
            <div>
              <p className="font-semibold text-foreground text-sm">Granny Halo</p>
              <div className="flex items-center gap-1">
                <svg viewBox="0 0 36 36" className="w-4 h-4" fill="hsl(214, 89%, 52%)">
                  <path d="M20.181 35.87C29.094 34.791 36 27.202 36 18c0-9.941-8.059-18-18-18S0 8.059 0 18c0 8.442 5.811 15.526 13.652 17.471L14 26h-4v-8h4v-5.5c0-4.694 2.806-7.5 7-7.5 1.778 0 3 .5 3 .5v4h-2c-1.95 0-3 1.313-3 3V18h5l-1 8h-4l.181 9.87z" />
                </svg>
                <span className="text-xs text-muted-foreground">Facebook</span>
              </div>
            </div>
          </div>

          {/* Options */}
          <div className="border border-border rounded-lg overflow-hidden mb-5">
            <label className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary transition-colors border-b border-border">
              <div>
                <p className="text-sm font-medium text-foreground">Get code via email</p>
                <p className="text-xs text-muted-foreground">granny1029381029@gmail.com</p>
              </div>
              <input
                type="radio"
                name="method"
                checked={method === "email"}
                onChange={() => setMethod("email")}
                className="w-5 h-5 accent-primary"
              />
            </label>
            <label className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary transition-colors">
              <div>
                <p className="text-sm font-medium text-foreground">Continue with password</p>
                <p className="text-xs text-muted-foreground">Use your password to continue</p>
              </div>
              <input
                type="radio"
                name="method"
                checked={method === "password"}
                onChange={() => setMethod("password")}
                className="w-5 h-5 accent-primary"
              />
            </label>
          </div>

          <div className="text-center mb-5">
            <a href="#" className="text-primary text-sm hover:underline">
              No longer have access to these?
            </a>
          </div>

          <button
            onClick={() => navigate("/confirm-account")}
            className="w-full py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-base hover:opacity-90 transition-opacity"
          >
            Continue
          </button>

          <button className="w-full mt-3 py-3 rounded-lg border border-border text-foreground font-semibold text-base hover:bg-secondary transition-colors">
            Not you?
          </button>
        </div>
      </main>
      <FooterLinks />
    </div>
  );
};

export default ChooseLogin;
