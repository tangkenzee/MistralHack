import { useState } from "react";
import BackButton from "@/components/BackButton";
import FooterLinks from "@/components/FooterLinks";

const ConfirmAccount = () => {
  const [code, setCode] = useState("");

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex flex-col items-center pt-10 px-4">
        <div className="w-full max-w-[580px]">
          <BackButton />
          <h1 className="text-2xl font-bold text-foreground mb-1">Confirm your account</h1>
          <p className="text-sm text-muted-foreground mb-5">
            We sent a code to your email address. Enter that code to confirm your account.
          </p>
          <input
            type="text"
            placeholder="Enter code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full px-4 py-3.5 border border-border rounded-lg text-base bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button className="w-full mt-4 py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-base hover:opacity-90 transition-opacity">
            Continue
          </button>
          <button className="w-full mt-3 py-3 rounded-lg border border-border text-foreground font-semibold text-base hover:bg-secondary transition-colors">
            Didn't get a code?
          </button>
        </div>
      </main>
      <FooterLinks />
    </div>
  );
};

export default ConfirmAccount;
